"""Real HTTP regressions for recovery plan/target evidence binding."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from gysam_observability import ObservabilityMCP


class RecoveryIdentityTests(unittest.TestCase):
    @contextmanager
    def backend(self, read_patch=None, apply_patch=None, omit_read=(), omit_apply=()):
        requests = []
        before = {'id': 'plan-1', 'target': 'configured-node', 'state': 'approved'}
        after = {**before, 'state': 'verified'}
        before.update(read_patch or {})
        after.update(apply_patch or {})
        for key in omit_read:
            before.pop(key, None)
        for key in omit_apply:
            after.pop(key, None)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def respond(self, payload):
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_GET(self):
                requests.append(('GET', self.path))
                self.respond(before)
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', 0)))
                requests.append(('POST', self.path))
                self.respond({'plan': after})
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {'GYSAM_OBSERVABILITY_TOKEN': 'test-only-token'}):
                app = ObservabilityMCP({'product': 'test', 'sources': [],
                    'backend': {'url': 'http://127.0.0.1:' + str(server.server_port), 'allow_local_http': True},
                    'enable_recovery': True,
                    'targets': {'node': 'configured-node', 'other': 'other-configured-node'}})
                yield app, requests
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

    def test_wrong_or_missing_read_identity_never_dispatches_apply(self):
        for value in ('different-plan', None, True, {}, ['plan-1']):
            with self.subTest(value=value), self.backend(read_patch={'id': value}) as (app, requests):
                with self.assertRaisesRegex(ValueError, '^invalid_backend_response$'):
                    app.call('recovery.apply', {'plan_id': 'plan-1'})
                self.assertEqual(requests, [('GET', '/api/v15/automation/plans/plan-1')])
        with self.backend(omit_read=('id',)) as (app, requests):
            with self.assertRaisesRegex(ValueError, '^invalid_backend_response$'):
                app.call('recovery.apply', {'plan_id': 'plan-1'})
            self.assertEqual(len(requests), 1)

    def test_apply_identity_or_target_mismatch_remains_uncertain_without_replay(self):
        for changed in ({'id': 'different-plan'}, {'id': None}, {'target': 'other-configured-node'},
                        {'target': None}, {'state': 'unrecognized'}, {'state': 'private backend details'}):
            with self.subTest(changed=changed), self.backend(apply_patch=changed) as (app, requests):
                with self.assertRaisesRegex(ValueError, '^backend_outcome_unknown$'):
                    app.call('recovery.apply', {'plan_id': 'plan-1'})
                self.assertEqual([entry[0] for entry in requests], ['GET', 'POST'])
        for key in ('id', 'target', 'state'):
            with self.subTest(missing=key), self.backend(omit_apply=(key,)) as (app, requests):
                with self.assertRaisesRegex(ValueError, '^backend_outcome_unknown$'):
                    app.call('recovery.apply', {'plan_id': 'plan-1'})
                self.assertEqual([entry[0] for entry in requests], ['GET', 'POST'])

    def test_invalid_read_state_is_not_reflected_or_used_for_dispatch(self):
        for state in ('private backend details', '', None, {}, 1):
            with self.subTest(state=state), self.backend(read_patch={'state': state}) as (app, requests):
                with self.assertRaisesRegex(ValueError, '^invalid_backend_response$'):
                    app.call('recovery.apply', {'plan_id': 'plan-1'})
                self.assertEqual(len(requests), 1)

    def test_valid_identity_preserves_verified_and_uncertain_states(self):
        for state in ('verified', 'failed', 'uncertain', 'simulated', 'verification_required'):
            with self.subTest(state=state), self.backend(apply_patch={'state': state}) as (app, requests):
                result = app.call('recovery.apply', {'plan_id': 'plan-1'})
                self.assertEqual(result['state'], state)
                self.assertEqual(result['verified'], state == 'verified')
                self.assertFalse(result['automatic_retry'])
                self.assertEqual([entry[0] for entry in requests], ['GET', 'POST'])


if __name__ == '__main__':
    unittest.main()
