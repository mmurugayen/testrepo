"""Terminal diagnostic outcomes preserve returns, exceptions and concurrency."""
import asyncio
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gysam_diagnostics as d


class OperationOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        capture = redirect_stderr(self.output)
        capture.__enter__()
        self.addCleanup(capture.__exit__, None, None, None)
        level = patch.dict(os.environ, {'GYSAM_LOG_LEVEL': 'DEBUG'})
        level.start()
        self.addCleanup(level.stop)
        d._logger.cache_clear()

    def rows(self):
        return [json.loads(line) for line in self.output.getvalue().splitlines() if line]

    def test_unsuccessful_result_has_one_timed_failure_even_when_slow(self):
        value = {'ok': False, 'payload': 'private-payload-token'}
        @d.observe('outcome-test')
        def work():
            return value
        with patch.object(d, 'monotonic', side_effect=[0, 2]):
            with d.log_context(request_id='request-1', job_id='job-1'):
                self.assertIs(work(), value)
        row, = self.rows()
        self.assertEqual((row['event'], row['level'], row['outcome']),
                         ('operation.failed', 'ERROR', 'failed'))
        self.assertEqual(row['reason'], 'unsuccessful_result')
        self.assertEqual(row['duration_ms'], 2000)
        self.assertEqual((row['request_id'], row['job_id']), ('request-1', 'job-1'))
        self.assertNotIn('private-payload-token', self.output.getvalue())
        self.assertEqual(d.current_context(), {})

    def test_success_and_false_like_results_keep_original_semantics(self):
        @d.observe('outcome-test')
        def work(value):
            return value
        values = [None, False, {'ok': True}, {'ok': 0}, {'ok': None}]
        for value in values:
            self.assertIs(work(value), value)
        self.assertEqual(len(self.rows()), len(values))
        self.assertTrue(all(row['event'] == 'operation.completed' and
                            row['outcome'] == 'completed' for row in self.rows()))

    def test_nested_failure_results_keep_separate_spans_and_one_event_each(self):
        @d.observe('outcome-test')
        def inner():
            return {'ok': False}
        @d.observe('outcome-test')
        def outer():
            return inner()
        outer()
        inner_row, outer_row = self.rows()
        self.assertEqual(inner_row['parent_span_id'], outer_row['span_id'])
        self.assertEqual([r['event'] for r in self.rows()], ['operation.failed'] * 2)

    def test_async_results_are_isolated_across_concurrent_calls(self):
        @d.observe('outcome-test')
        async def work(value):
            await asyncio.sleep(0)
            return value
        async def invoke(request_id, value):
            with d.log_context(request_id=request_id):
                self.assertIs(await work(value), value)
            self.assertEqual(d.current_context(), {})
        async def exercise():
            await asyncio.gather(invoke('failed-1', {'ok': False}),
                                 invoke('success-1', {'ok': True}))
        asyncio.run(exercise())
        rows = {r['request_id']: r for r in self.rows()}
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(rows['failed-1']['event'], 'operation.failed')
        self.assertEqual(rows['success-1']['event'], 'operation.completed')
        self.assertNotEqual(rows['failed-1']['span_id'], rows['success-1']['span_id'])

    def test_exception_and_cancellation_keep_identity_and_private_message(self):
        for error in [ValueError('private-exception-token'), asyncio.CancelledError()]:
            @d.observe('outcome-test')
            async def work():
                raise error
            async def exercise():
                with self.assertRaises(type(error)) as caught:
                    await work()
                self.assertIs(caught.exception, error)
                self.assertEqual(d.current_context(), {})
            asyncio.run(exercise())
        self.assertEqual([r['outcome'] for r in self.rows()], ['failed', 'interrupted'])
        self.assertTrue(all('duration_ms' in r for r in self.rows()))
        self.assertNotIn('private-exception-token', self.output.getvalue())

    def test_broken_sink_preserves_unsuccessful_result(self):
        class Broken:
            def write(self, _):
                raise OSError('sink-unavailable')
        value = {'ok': False}
        @d.observe('outcome-test')
        def work():
            return value
        with patch.object(sys, 'stderr', Broken()):
            self.assertIs(work(), value)
        # Reconcile both changes: recovery is metadata, followed by exactly one
        # timed failure event, and handler state does not escape this scenario.
        self.assertIs(work(), value)
        recovery, failure = self.rows()
        self.assertEqual((recovery['event'], recovery['count']),
                         ('diagnostic.sink.recovered', 1))
        self.assertEqual((failure['event'], failure['outcome']),
                         ('operation.failed', 'failed'))
        self.assertIn('duration_ms', failure)
        self.assertEqual(d.current_context(), {})


if __name__ == '__main__':
    unittest.main()
