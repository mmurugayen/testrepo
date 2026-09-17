"""Exercise every shipped diagnostic copy against operation lifecycle contracts."""
import asyncio
from contextlib import redirect_stderr
import importlib.util
import inspect
import io
import json
import logging
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COPIES = (
    'scripts/gysam_diagnostics.py',
    'packages/runtime/gysam/diagnostics.py',
    'releases/v14.3.5/source/gysam_runtime/diagnostics.py',
    'backend/app/core/diagnostics.py',
    'gysam_veyon/diagnostics.py',
)


class SpanContract:
    def setUp(self):
        # Python's logging registry outlives dynamically loaded module copies.
        # A failed sink in one copy must not seed another copy's test interval.
        logger = logging.getLogger('gysam.diagnostics.span-contract')
        previous_handlers = logger.handlers[:]
        previous_level, previous_propagate = logger.level, logger.propagate
        logger.handlers = []
        def restore_logger():
            logger.handlers = previous_handlers
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate
        self.addCleanup(restore_logger)
        spec = importlib.util.spec_from_file_location('span_contract', ROOT / self.copy_path)
        self.d = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.d)
        self.output = io.StringIO()
        redirect = redirect_stderr(self.output)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)
        setting = patch.dict(os.environ, {'GYSAM_LOG_LEVEL': 'DEBUG'})
        setting.start()
        self.addCleanup(setting.stop)
        self.d._logger.cache_clear()

    def rows(self):
        return [json.loads(line) for line in self.output.getvalue().splitlines() if line]

    def test_fast_and_slow_failed_results_have_only_one_terminal_event(self):
        d = self.d
        value = {'ok': False, 'payload': 'private-result-marker'}
        @d.observe('span-contract')
        def work():
            return value
        for elapsed in (0.01, 2):
            with patch.object(d, 'monotonic', side_effect=[0, elapsed]):
                self.assertIs(work(), value)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['event'] for r in rows], ['operation.failed'] * 2)
        self.assertEqual([r['outcome'] for r in rows], ['failed'] * 2)
        self.assertEqual([r['duration_ms'] for r in rows], [10, 2000])
        self.assertNotIn('private-result-marker', self.output.getvalue())
        self.assertEqual(d.current_context(), {})

    def test_nested_success_keeps_parent_and_restores_caller_context(self):
        d = self.d
        contexts = []
        @d.observe('span-contract')
        def child():
            contexts.append(d.current_context())
            return 3
        @d.observe('span-contract')
        def parent():
            contexts.append(d.current_context())
            self.assertEqual(child(), 3)
            self.assertEqual(d.current_context(), contexts[0])
        with d.log_context(request_id='request-1', span_id='upstream', scope_ref='a' * 64):
            before = d.current_context()
            parent()
            self.assertEqual(d.current_context(), before)
        outer, inner = contexts
        self.assertEqual(outer['parent_span_id'], 'upstream')
        self.assertEqual(inner['parent_span_id'], outer['span_id'])
        self.assertNotEqual(inner['span_id'], outer['span_id'])
        self.assertEqual(inner['request_id'], 'request-1')
        if 'scope_ref' in before:
            self.assertEqual(inner['scope_ref'], before['scope_ref'])
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(d.current_context(), {})

    def test_exception_identity_redaction_and_next_call_recovery(self):
        d = self.d
        error = ValueError('private-exception-marker')
        @d.observe('span-contract')
        def work(fail):
            if fail:
                raise error
            return 17
        with d.log_context(request_id='recovery-1'):
            before = d.current_context()
            with self.assertRaises(ValueError) as caught:
                work(True)
            self.assertIs(caught.exception, error)
            self.assertEqual(d.current_context(), before)
            self.assertEqual(work(False), 17)
            self.assertEqual(d.current_context(), before)
        rows = self.rows()
        self.assertEqual([r['outcome'] for r in rows], ['failed', 'completed'])
        self.assertNotEqual(rows[0]['span_id'], rows[1]['span_id'])
        self.assertNotIn('private-exception-marker', self.output.getvalue())

    def test_concurrent_async_cancellation_preserves_sibling_context(self):
        d = self.d
        seen = {}
        @d.observe('span-contract')
        async def worker(name, entered, release):
            seen[name] = d.current_context()
            entered.set()
            try:
                await release.wait()
                self.assertEqual(d.current_context(), seen[name])
                return name
            finally:
                self.assertEqual(d.current_context(), seen[name])
        async def exercise():
            a, b, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
            with d.log_context(request_id='async-1', span_id='caller'):
                before = d.current_context()
                one = asyncio.create_task(worker('one', a, release))
                two = asyncio.create_task(worker('two', b, release))
                await a.wait()
                await b.wait()
                one.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await one
                self.assertEqual(d.current_context(), before)
                release.set()
                self.assertEqual(await two, 'two')
                self.assertEqual(d.current_context(), before)
            self.assertEqual(d.current_context(), {})
        asyncio.run(exercise())
        self.assertNotEqual(seen['one']['span_id'], seen['two']['span_id'])
        self.assertEqual(seen['one']['parent_span_id'], 'caller')
        self.assertEqual(seen['two']['parent_span_id'], 'caller')
        self.assertEqual([r['outcome'] for r in self.rows()], ['interrupted', 'completed'])

    def test_async_failed_result_has_one_terminal_event(self):
        d = self.d
        value = {'ok': False}
        @d.observe('span-contract')
        async def work():
            return value
        self.assertIs(asyncio.run(work()), value)
        self.assertEqual([r['outcome'] for r in self.rows()], ['failed'])
        self.assertEqual(d.current_context(), {})

    def test_filtering_and_slow_success_threshold(self):
        d = self.d
        @d.observe('span-contract')
        def work():
            return 23
        with patch.dict(os.environ, {'GYSAM_LOG_LEVEL': 'INFO'}):
            d._logger.cache_clear()
            for elapsed in (0.999, 1):
                with patch.object(d, 'monotonic', side_effect=[0, elapsed]):
                    self.assertEqual(work(), 23)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['level'], 'WARNING')
        self.assertEqual(rows[0]['duration_ms'], 1000)

    def test_sink_failure_preserves_result_and_exception(self):
        d = self.d
        class BrokenSink:
            def write(self, value):
                raise OSError('unavailable')
            def flush(self):
                raise OSError('unavailable')
        error = RuntimeError('business-error')
        @d.observe('span-contract')
        def work(fail):
            if fail:
                raise error
            return {'ok': False}
        with redirect_stderr(BrokenSink()):
            self.assertEqual(work(False), {'ok': False})
            with self.assertRaises(RuntimeError) as caught:
                work(True)
            self.assertIs(caught.exception, error)
        self.assertEqual(d.current_context(), {})

    def test_descriptors_signature_and_generator_lifetimes(self):
        d = self.d
        class Service:
            @staticmethod
            def echo(value=3):
                return value
            @classmethod
            def owner(cls):
                return cls
        before = inspect.signature(Service.echo)
        d.observe_class(Service, 'span-contract')
        first = Service.echo
        d.observe_class(Service, 'span-contract')
        self.assertIs(first, Service.echo)
        self.assertEqual(inspect.signature(Service.echo), before)
        self.assertEqual(Service.echo(), 3)
        self.assertIs(Service.owner(), Service)
        def stream():
            yield 1
        async def astream():
            yield 1
        self.assertIs(d.observe('span-contract')(stream), stream)
        self.assertIs(d.observe('span-contract')(astream), astream)


for index, path in enumerate(COPIES):
    if (ROOT / path).is_file():
        name = 'SpanCopy' + str(index) + 'Tests'
        globals()[name] = type(name, (SpanContract, unittest.TestCase), {'copy_path': path})


if __name__ == '__main__':
    unittest.main()
