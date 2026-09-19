"""Composed buffered WSGI diagnostics preserve one request identity."""
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


class WSGIRequestCorrelationTests(unittest.TestCase):
    def setUp(self):
        level = patch.dict(os.environ, {'GYSAM_LOG_LEVEL': 'INFO'})
        level.start()
        self.addCleanup(level.stop)
        d._logger.cache_clear()

    def test_composed_wsgi_reuses_request_id_in_logs_and_response(self):
        body = [b'unchanged-body']
        class App:
            @d.wsgi_logging('wsgi-outer')
            def outer(self, environ, start_response):
                return self.inner(environ, start_response)

            @d.wsgi_logging('wsgi-inner')
            def inner(self, environ, start_response):
                start_response('200 OK', [('Content-Type', 'text/plain'),
                                         ('X-Request-ID', 'untrusted-app-id')])
                return body

        generated = []
        for incoming in (None, 'invalid private request id', b'bytes-id', 'valid-id'):
            with self.subTest(incoming=incoming):
                environ = {'REQUEST_METHOD': 'GET'}
                if incoming is not None:
                    environ['HTTP_X_REQUEST_ID'] = incoming
                output, responses = io.StringIO(), []
                def start_response(status, headers):
                    responses.append((status, headers))
                with d.log_context(request_id='outside-request'):
                    with redirect_stderr(output):
                        self.assertIs(App().outer(environ, start_response), body)
                    self.assertEqual(d.current_context()['request_id'], 'outside-request')
                rows = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual([row['service'] for row in rows], ['wsgi-inner', 'wsgi-outer'])
                self.assertEqual(len(responses), 1)
                status, headers = responses[0]
                self.assertEqual(status, '200 OK')
                self.assertIn(('Content-Type', 'text/plain'), headers)
                ids = [value for key, value in headers if key.lower() == 'x-request-id']
                self.assertEqual(len(ids), 1)
                ident = ids[0]
                self.assertEqual([row['request_id'] for row in rows], [ident, ident])
                self.assertEqual([row['correlation_id'] for row in rows], [ident, ident])
                self.assertEqual(environ['gysam.request_id'], ident)
                self.assertNotIn('invalid private request id', output.getvalue())
                self.assertNotIn('untrusted-app-id', output.getvalue())
                if incoming == 'valid-id':
                    self.assertEqual(ident, incoming)
                else:
                    self.assertNotIn(ident, generated)
                    generated.append(ident)
                self.assertEqual(d.current_context(), {})

    def test_composed_wsgi_failure_preserves_exception_and_outer_context(self):
        failure = RuntimeError('private-exception-detail')
        class App:
            @d.wsgi_logging('wsgi-outer')
            def outer(self, environ, start_response):
                return self.inner(environ, start_response)

            @d.wsgi_logging('wsgi-inner')
            def inner(self, environ, start_response):
                raise failure

        output = io.StringIO()
        environ = {'REQUEST_METHOD': 'GET'}
        with d.log_context(request_id='outside-request'):
            with redirect_stderr(output), self.assertRaises(RuntimeError) as caught:
                App().outer(environ, lambda *args: self.fail('unexpected response'))
            self.assertIs(caught.exception, failure)
            self.assertEqual(d.current_context()['request_id'], 'outside-request')
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual({row['request_id'] for row in rows}, {environ['gysam.request_id']})
        self.assertEqual([row['level'] for row in rows], ['ERROR', 'ERROR'])
        self.assertNotIn('private-exception-detail', output.getvalue())
        self.assertEqual(d.current_context(), {})


if __name__ == '__main__':
    unittest.main()
