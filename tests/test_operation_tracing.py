"""Operation tracing preserves call semantics, context and secret boundaries."""
import asyncio
from contextlib import redirect_stderr
import importlib
import inspect
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
d = importlib.import_module('gysam_diagnostics')


class OperationTracingTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        redirect = redirect_stderr(self.output)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)
        setting = patch.dict(os.environ, {'GYSAM_LOG_LEVEL': 'DEBUG'})
        setting.start()
        self.addCleanup(setting.stop)
        d._logger.cache_clear()

    def rows(self):
        return [json.loads(line) for line in self.output.getvalue().splitlines()]

    def test_nested_failure_has_parent_span_and_never_logs_arguments(self):
        marker = uuid4().hex
        @d.observe('trace-test')
        def inner(value):
            raise RuntimeError(value)
        @d.observe('trace-test')
        def outer(value):
            return inner(value)
        with d.log_context(request_id='edge-1'):
            with self.assertRaisesRegex(RuntimeError, marker):
                outer(marker)
        inner_row, outer_row = self.rows()
        self.assertEqual(inner_row['parent_span_id'], outer_row['span_id'])
        self.assertEqual(inner_row['request_id'], 'edge-1')
        self.assertNotIn(marker, self.output.getvalue())
        self.assertEqual(d.current_context(), {})

    def test_unsuccessful_adapter_result_is_visible_without_serializing_it(self):
        marker = uuid4().hex
        value = {'ok': False, 'payload': marker}
        @d.observe('trace-test')
        def call():
            return value
        self.assertIs(call(), value)
        failures = [row for row in self.rows() if row['level'] == 'ERROR']
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['reason'], 'unsuccessful_result')
        self.assertNotIn(marker, self.output.getvalue())

    def test_results_signatures_and_descriptors_are_preserved(self):
        sentinel = object()
        class Service:
            def call(self, value=sentinel):
                return value
            @classmethod
            def owner(cls):
                return cls
            @staticmethod
            def static(value):
                return value
        before = inspect.signature(Service.call)
        d.observe_class(Service, 'trace-test')
        first = Service.call
        d.observe_class(Service, 'trace-test')
        self.assertIs(first, Service.call)
        self.assertEqual(inspect.signature(Service.call), before)
        self.assertIs(Service().call(), sentinel)
        self.assertIs(Service.owner(), Service)
        self.assertIs(Service.static(sentinel), sentinel)

    def test_generator_lifetime_is_not_shortened(self):
        def stream():
            yield 1
            raise ValueError('end')
        self.assertIs(d.observe('trace-test')(stream), stream)
        iterator = stream()
        self.assertEqual(next(iterator), 1)
        with self.assertRaises(ValueError):
            next(iterator)

    def test_async_cancellation_propagates_and_context_resets(self):
        @d.observe('trace-test')
        async def work():
            raise asyncio.CancelledError()
        async def exercise():
            with self.assertRaises(asyncio.CancelledError):
                await work()
            self.assertEqual(d.current_context(), {})
        asyncio.run(exercise())
        self.assertEqual(self.rows()[0]['error_type'], 'CancelledError')

    def test_success_is_debug_until_one_second(self):
        @d.observe('trace-test')
        def work():
            return 7
        with patch.object(d, 'monotonic', side_effect=[0, .1]):
            self.assertEqual(work(), 7)
        with patch.object(d, 'monotonic', side_effect=[0, 2]):
            self.assertEqual(work(), 7)
        self.assertEqual([row['level'] for row in self.rows()], ['DEBUG', 'WARNING'])


if __name__ == '__main__':
    unittest.main()
