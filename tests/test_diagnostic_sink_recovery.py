"""Diagnostic sink outage accounting must not replay events or change outcomes."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import io
import json
import logging
from pathlib import Path
import sys
from threading import Event
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gysam_diagnostics as d


class BrokenStream:
    def write(self, text):
        raise OSError('customer-secret')


class SinkRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.handler = d._StderrHandler('sink-test')
        self.record = logging.LogRecord('sink-test', logging.INFO, '', 0,
                                       '{"event":"business.completed"}', (), None)

    def send(self, stream):
        with patch.object(sys, 'stderr', stream):
            self.handler.handle(self.record)

    def rows(self, stream):
        return [json.loads(line) for line in stream.getvalue().splitlines() if line]

    def test_failed_writes_recover_once_without_replay_or_scope_leak(self):
        for _ in range(3):
            self.send(BrokenStream())
        out = io.StringIO()
        with d.log_context(request_id='private-request', scope_ref='private-scope'):
            self.send(out)
        self.send(out)
        rows = self.rows(out)
        self.assertEqual([r['event'] for r in rows],
                         ['diagnostic.sink.recovered', 'business.completed', 'business.completed'])
        self.assertEqual(rows[0]['count'], 3)
        self.assertEqual(rows[0]['reason'], 'interrupted_record_attempts')
        self.assertNotIn('private', out.getvalue())
        self.assertNotIn('customer-secret', out.getvalue())
        self.assertEqual(self.handler.failed_attempts, 0)

    def test_flush_failure_is_ambiguous_and_not_replayed(self):
        class FlushFailure(io.StringIO):
            def flush(self):
                raise OSError('flush-secret')
        first = FlushFailure()
        self.send(first)
        self.assertEqual(self.rows(first), [{'event': 'business.completed'}])
        out = io.StringIO()
        self.send(out)
        self.assertEqual(self.rows(out)[0]['count'], 1)
        self.assertEqual(len(self.rows(out)), 2)

    def test_write_requires_exact_integer_acknowledgement(self):
        class IntegerLike(int):
            pass
        class InvalidAck:
            flushed = False
            def write(self, text):
                return acknowledgement
            def flush(self):
                self.flushed = True
        # A one-character write catches True comparing equal to length 1.
        for acknowledgement in (None, True, False, 1.0, '1', IntegerLike(1)):
            with self.subTest(acknowledgement=repr(acknowledgement)):
                stream = InvalidAck()
                with self.assertRaises(OSError):
                    self.handler._write(stream, '\n')
                self.assertFalse(stream.flushed)

    def test_missing_acknowledgement_keeps_recovery_pending_without_replay(self):
        class MissingAck(io.StringIO):
            def write(self, text):
                super().write(text)
                return None
        first = MissingAck()
        self.send(first)
        self.assertEqual(self.handler.failed_attempts, 1)
        self.assertEqual(self.rows(first), [{'event': 'business.completed'}])
        recovery = MissingAck()
        self.send(recovery)
        self.assertEqual(self.handler.failed_attempts, 2)
        self.assertEqual([r['event'] for r in self.rows(recovery)],
                         ['diagnostic.sink.recovered'])
        out = io.StringIO()
        self.send(out)
        self.assertEqual(self.rows(out)[0]['count'], 2)
        self.assertEqual([r['event'] for r in self.rows(out)],
                         ['diagnostic.sink.recovered', 'business.completed'])
        self.assertEqual(self.handler.failed_attempts, 0)

    def test_short_write_recovery_starts_a_complete_new_line(self):
        class ShortWrite(io.StringIO):
            broken = True
            def write(self, text):
                return super().write(text[:5] if self.broken else text)
        out = ShortWrite()
        self.send(out)
        out.broken = False
        self.send(out)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], '{"eve')
        self.assertEqual(json.loads(lines[1])['event'], 'diagnostic.sink.recovered')
        self.assertEqual(json.loads(lines[2])['event'], 'business.completed')

    def test_failed_recovery_counts_current_event_and_keeps_pending_count(self):
        self.send(BrokenStream())
        self.send(BrokenStream())
        out = io.StringIO()
        self.send(out)
        self.assertEqual(self.rows(out)[0]['count'], 2)
        self.assertEqual(len(self.rows(out)), 2)

    def test_concurrent_failures_are_counted_and_counter_saturates(self):
        with patch.object(sys, 'stderr', BrokenStream()):
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda _: self.handler.handle(self.record), range(200)))
        self.assertEqual(self.handler.failed_attempts, 200)
        self.handler.failed_attempts = 2**53 - 1
        self.send(BrokenStream())
        self.assertEqual(self.handler.failed_attempts, 2**53 - 1)
        out = io.StringIO()
        self.send(out)
        count = self.rows(out)[0]['count']
        self.assertIs(type(count), int)
        self.assertEqual(count, 2**53 - 1)
        self.assertEqual(int(float(count)), count)

    def test_recovery_then_new_failure_starts_another_interval(self):
        class SecondWriteFailure(io.StringIO):
            writes = 0
            def write(self, text):
                self.writes += 1
                if self.writes == 2:
                    raise OSError('private')
                return super().write(text)
        self.send(BrokenStream())
        out = SecondWriteFailure()
        self.send(out)
        self.assertEqual(self.rows(out)[0]['count'], 1)
        self.assertEqual(self.handler.failed_attempts, 1)
        self.send(out)
        self.assertEqual([r['event'] for r in self.rows(out)],
                         ['diagnostic.sink.recovered', 'diagnostic.sink.recovered', 'business.completed'])

    def test_a_different_service_recovers_the_shared_sink_without_losing_its_event(self):
        class ShortWrite(io.StringIO):
            broken = True
            def write(self, text):
                return super().write(text[:8] if self.broken else text)
        with patch.object(d._STDERR_HANDLER, 'failed_attempts', 0):
            output = ShortWrite()
            with patch.object(sys, 'stderr', output):
                d.emit('cross-service-a', 'operation.interrupted')
                output.broken = False
                d.emit('cross-service-b', 'operation.returned')
            lines = output.getvalue().splitlines()
            recovery, event = [json.loads(line) for line in lines[1:]]
            self.assertEqual((recovery['event'], recovery['count']),
                             ('diagnostic.sink.recovered', 1))
            self.assertEqual(recovery['service'], 'gysam-diagnostics')
            self.assertEqual(event['service'], 'cross-service-b')
            self.assertEqual(event['event'], 'operation.returned')
            self.assertEqual(d._STDERR_HANDLER.failed_attempts, 0)

    def test_concurrent_service_cannot_append_before_a_short_write_is_accounted(self):
        entered, release, second_started = Event(), Event(), Event()
        class PausedShortWrite(io.StringIO):
            first = True
            def write(self, text):
                if self.first:
                    self.first = False
                    written = super().write(text[:8])
                    entered.set()
                    if not release.wait(3):
                        raise RuntimeError('test_write_release_timeout')
                    return written
                return super().write(text)
        def second():
            second_started.set()
            d.emit('concurrent-service-b', 'operation.returned')
        output = PausedShortWrite()
        with patch.object(d._STDERR_HANDLER, 'failed_attempts', 0), patch.object(sys, 'stderr', output):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(d.emit, 'concurrent-service-a', 'operation.interrupted')
                try:
                    self.assertTrue(entered.wait(3))
                    other = pool.submit(second)
                    self.assertTrue(second_started.wait(3))
                    with self.assertRaises(TimeoutError):
                        other.result(timeout=0.05)
                finally:
                    release.set()
                first.result(timeout=3)
                other.result(timeout=3)
        recovery, event = [json.loads(line) for line in output.getvalue().splitlines()[1:]]
        self.assertEqual((recovery['event'], recovery['count']),
                         ('diagnostic.sink.recovered', 1))
        self.assertEqual(event['service'], 'concurrent-service-b')
        self.assertEqual(event['event'], 'operation.returned')

    def test_normal_emit_keeps_one_write_and_original_business_outcome(self):
        class CountingStream(io.StringIO):
            writes = 0
            def write(self, text):
                self.writes += 1
                return super().write(text)
        logger = logging.Logger('isolated', logging.DEBUG)
        logger.addHandler(self.handler)
        @d.observe('sink-test')
        def operation():
            return 'original-result'
        with patch.object(d, '_logger', return_value=logger):
            with patch.object(sys, 'stderr', BrokenStream()):
                self.assertEqual(operation(), 'original-result')
            out = CountingStream()
            with patch.object(sys, 'stderr', out):
                self.assertEqual(operation(), 'original-result')
                before = out.writes
                self.assertEqual(operation(), 'original-result')
            self.assertEqual(out.writes - before, 1)
            self.assertEqual(self.rows(out)[0]['event'], 'diagnostic.sink.recovered')


    def test_non_integer_write_results_are_not_success_acknowledgments(self):
        class Unconfirmed(io.StringIO):
            def __init__(self, result):
                super().__init__()
                self.result = result

            def write(self, text):
                return self.result(len(text))

        for result in (lambda _: None, lambda size: float(size), lambda _: True, lambda _: 'complete'):
            with self.subTest(result=result):
                self.send(Unconfirmed(result))
        self.assertEqual(self.handler.failed_attempts, 4)
        out = io.StringIO()
        self.send(out)
        self.assertEqual(self.rows(out)[0]['count'], 4)

    def test_failed_recovery_flush_keeps_current_attempt_pending(self):
        class FlushFailure(io.StringIO):
            def flush(self):
                raise OSError('private-recovery-flush')

        self.send(BrokenStream())
        ambiguous = FlushFailure()
        self.send(ambiguous)
        self.assertEqual(self.handler.failed_attempts, 2)
        self.assertEqual([row['event'] for row in self.rows(ambiguous)],
                         ['diagnostic.sink.recovered'])
        out = io.StringIO()
        self.send(out)
        self.assertEqual(self.rows(out)[0]['count'], 2)
        self.assertEqual([row['event'] for row in self.rows(out)],
                         ['diagnostic.sink.recovered', 'business.completed'])
        self.assertNotIn('private', out.getvalue())


if __name__ == '__main__':
    unittest.main()
