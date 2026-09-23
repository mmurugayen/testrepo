"""Bounded JSON diagnostics shared by Gysam services (schema version 1).

Only explicit diagnostic fields are accepted. Never pass payloads, credentials,
exception messages or command output. Audit/evidence storage remains authoritative.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import lru_cache, wraps
import json
import logging
import math
import os
from pathlib import PurePath
import re
import sys
from threading import RLock
from time import monotonic
from uuid import uuid4

_ID = re.compile(r'^[A-Za-z0-9._-]{1,64}$')
_NAME = re.compile(r'^[A-Za-z0-9._-]{1,96}$')
_FIELDS = frozenset(('component', 'operation', 'outcome', 'reason', 'request_id',
    'correlation_id', 'run_id', 'job_id', 'operation_id', 'evidence_id',
    'delivery_id', 'ticket_id', 'worker_id', 'attempt', 'retryable', 'status_code',
    'duration_ms', 'count', 'exit_code', 'method', 'span_id', 'parent_span_id', 'plan_id'))
_CONTEXT = ContextVar('gysam_diagnostic_context', default=None)
_CONFIG_LOCK = RLock()
# Exact in JSON consumers and bounded by the diagnostic scalar contract.
_COUNTER_LIMIT = 2**53 - 1
_REVISION = os.environ.get('GYSAM_REVISION') or os.environ.get('GITHUB_SHA', '')
_REVISION = _REVISION.lower() if re.fullmatch(r'[A-Fa-f0-9]{40}', _REVISION) else None
# Never include tenant/site names, URLs or arbitrary environment values.
_RUN_ID = (os.environ.get('GYSAM_RUN_ID') or '')
if not _ID.fullmatch(_RUN_ID):
    ci_run = os.environ.get('GITHUB_RUN_ID', '')
    ci_attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    candidate = 'gh-' + ci_run + '-' + ci_attempt
    _RUN_ID = candidate if ci_run.isdecimal() and ci_attempt.isdecimal() and _ID.fullmatch(candidate) else uuid4().hex


def normalize_request_id(value):
    return value if isinstance(value, str) and _ID.fullmatch(value) else uuid4().hex


def current_context():
    return dict(_CONTEXT.get() or {})


def _safe_fields(fields):
    result = {}
    for key, value in fields.items():
        if key not in _FIELDS:
            continue
        if type(value) in (bool, int):
            if type(value) is bool or abs(value) < 10**16:
                result[key] = value
        elif type(value) is float:
            if math.isfinite(value) and abs(value) < 10**16:
                result[key] = round(value, 3)
        elif isinstance(value, str) and _NAME.fullmatch(value):
            result[key] = value
    return result


@contextmanager
def log_context(**fields):
    token = _CONTEXT.set({**current_context(), **_safe_fields(fields)})
    try:
        yield
    finally:
        _CONTEXT.reset(token)


class _StderrHandler(logging.Handler):
    """Report interrupted writes on recovery without buffering or replaying events."""
    def __init__(self, service):
        super().__init__()
        self.service = service
        # Handler.handle serializes emit calls. Saturate rather than retaining
        # failed records, scope identifiers, exceptions or an unbounded counter.
        self.failed_attempts = 0

    @staticmethod
    def _write(stream, text):
        written = stream.write(text)
        if type(written) is not int or written != len(text):
            raise OSError('diagnostic_short_write')
        stream.flush()

    def emit(self, record):
        try:
            stream = sys.stderr
            if self.failed_attempts:
                recovery = {
                    'schema_version': 1,
                    'timestamp': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                    'level': 'WARNING', 'service': self.service,
                    'event': 'diagnostic.sink.recovered', 'run_id': _RUN_ID,
                    'count': self.failed_attempts,
                    'reason': 'interrupted_record_attempts',
                }
                if _REVISION:
                    recovery['revision'] = _REVISION
                # A prior short write may have left a partial JSON line. Keep
                # the recovery marker parseable without replaying that record.
                self._write(stream, '\n' + json.dumps(recovery, separators=(',', ':')) + '\n')
                self.failed_attempts = 0
            self._write(stream, record.getMessage() + '\n')
        except Exception:
            # A failed flush has ambiguous delivery; this is an interrupted
            # attempt count, never a claim that exactly this many logs were lost.
            self.failed_attempts = min(self.failed_attempts + 1, _COUNTER_LIMIT)


# All built-in diagnostic loggers write to the same stream. Share its handler
# lock and failure interval so recovery also frames a different service's event.
_STDERR_HANDLER = _StderrHandler('gysam-diagnostics')


@lru_cache(maxsize=32)
def _logger(service, logger_name=None):
    with _CONFIG_LOCK:
        logger = logging.getLogger(logger_name or ('gysam.diagnostics.' + service))
        if not logger.handlers:
            logger.addHandler(_STDERR_HANDLER)
        logger.propagate = False
        # Invalid levels fall back to INFO. Do not reconfigure application/root logs.
        level = os.environ.get('GYSAM_LOG_LEVEL', 'INFO').upper()
        logger.setLevel(getattr(logging, level, logging.INFO) if level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') else logging.INFO)
        return logger


def emit(service, event, *, level='INFO', error=None, logger_name=None, **fields):
    """Emit one bounded line; exception type/locations exclude messages and locals."""
    try:
        if not _NAME.fullmatch(service) or not _NAME.fullmatch(event):
            return
        if level not in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
            level = 'INFO'
        severity = getattr(logging, level)
        logger = _logger(service, logger_name)
        if not logger.isEnabledFor(severity):
            return
        record = {'schema_version': 1, 'timestamp': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                  'level': level, 'service': service, 'event': event, 'run_id': _RUN_ID,
                  **current_context(), **_safe_fields(fields)}
        if _REVISION:
            record['revision'] = _REVISION
        if record.get('request_id'):
            record.setdefault('correlation_id', record['request_id'])
        if error is not None:
            record['error_type'] = type(error).__name__[:96]
            frames = []
            tb = error.__traceback__
            while tb is not None:
                # Code location only: source text, locals and exception strings can contain secrets.
                code = tb.tb_frame.f_code
                frames.append({'file': PurePath(code.co_filename).name[:96],
                               'function': code.co_name[:96], 'line': tb.tb_lineno})
                if len(frames) > 8:
                    del frames[0]
                tb = tb.tb_next
            record['error_frames'] = frames
        logger.log(severity, json.dumps(record, separators=(',', ':'), ensure_ascii=True, allow_nan=False))
    except Exception:
        pass


def _request_fields(scope, header_key):
    # Duplicate or non-ASCII IDs are replaced, never concatenated/truncated.
    values = [v for k, v in scope.get('headers', ()) if k.lower() == header_key]
    try:
        incoming = values[0].decode('ascii') if len(values) == 1 else None
    except (UnicodeError, AttributeError):
        incoming = None
    return normalize_request_id(incoming)


def _completion(service, started, status, error=None, **fields):
    level = 'ERROR' if error is not None or status >= 500 else 'WARNING' if status >= 400 else 'INFO'
    emit(service, 'http.request.completed', level=level, error=error,
         status_code=status, duration_ms=(monotonic()-started)*1000, **fields)


def asgi_logging(service):
    """Instrument an ASGI method without consuming/buffering bodies or retrying I/O."""
    def decorate(function):
        @wraps(function)
        async def wrapped(self, scope, receive, send):
            if scope['type'] != 'http':
                return await function(self, scope, receive, send)
            request_id = _request_fields(scope, b'x-request-id')
            # Use the same safe ID in composed middleware stacks.
            scope['gysam.request_id'] = request_id
            scope['headers'] = [(k, v) for k, v in scope.get('headers', ()) if k.lower() != b'x-request-id'] + [(b'x-request-id', request_id.encode('ascii'))]
            started, status, error, completed = monotonic(), 499, None, False
            async def contextual_send(message):
                nonlocal status, completed
                if message['type'] == 'http.response.start':
                    status = message['status']
                    message = dict(message)
                    message['headers'] = [(k, v) for k, v in message.get('headers', ()) if k.lower() != b'x-request-id'] + [(b'x-request-id', request_id.encode('ascii'))]
                await send(message)
                if message['type'] == 'http.response.body' and not message.get('more_body', False):
                    completed = True
            with log_context(request_id=request_id):
                try:
                    return await function(self, scope, receive, contextual_send)
                except BaseException as exc:
                    error = exc
                    if not completed:
                        status = 500 if isinstance(exc, Exception) else 499
                    raise
                finally:
                    _completion(service, started, status, error, method=scope.get('method'),
                                outcome='completed' if completed else 'interrupted',
                                operation=getattr(scope.get('route'), 'name', None))
        return wrapped
    return decorate


def wsgi_logging(service):
    """Instrument the repository's buffered WSGI APIs, preserving their list result."""
    def decorate(function):
        @wraps(function)
        def wrapped(self, environ, start_response):
            request_id = normalize_request_id(environ.get('HTTP_X_REQUEST_ID'))
            environ['gysam.request_id'] = request_id
            started, status, error = monotonic(), 500, None
            def contextual_start(value, headers, exc_info=None):
                nonlocal status
                status = int(value.split(' ', 1)[0])
                headers = [(k, v) for k, v in headers if k.lower() != 'x-request-id'] + [('X-Request-ID', request_id)]
                return start_response(value, headers, exc_info) if exc_info else start_response(value, headers)
            with log_context(request_id=request_id):
                try:
                    return function(self, environ, contextual_start)
                except BaseException as exc:
                    error = exc
                    raise
                finally:
                    _completion(service, started, status, error, method=environ.get('REQUEST_METHOD'))
        return wrapped
    return decorate


def observe(service):
    """Trace public operations without serializing arguments, results or locals.

    Failures always follow ERROR filtering. Successful spans are DEBUG, while
    operations taking at least one second emit WARNING. Generators keep their
    original lifetime and are traced by their consuming operation boundary.
    """
    def decorate(function):
        import inspect
        if getattr(function, '_gysam_observed', False):
            return function
        original = inspect.unwrap(function)
        if inspect.isgeneratorfunction(original) or inspect.isasyncgenfunction(original):
            return function
        component = function.__module__
        operation = function.__qualname__.replace('<', '').replace('>', '')

        def start_span():
            # Existing context has already passed log_context's field filter.
            # Copy once: never mutate the dictionary inherited by another task.
            context = current_context()
            parent = context.get('span_id')
            started = monotonic()
            context['span_id'] = uuid4().hex
            if parent is not None:
                context['parent_span_id'] = parent
            return started, _CONTEXT.set(context)

        def failed(error, started):
            emit(service, 'operation.failed', level='ERROR', error=error,
                 component=component, operation=operation,
                 outcome='interrupted' if not isinstance(error, Exception) else 'failed',
                 duration_ms=(monotonic() - started) * 1000)

        def result_value(result, started):
            # One terminal event per boundary, including a slow returned failure.
            elapsed = (monotonic() - started) * 1000
            if type(result) is dict and result.get('ok') is False:
                emit(service, 'operation.failed', level='ERROR', reason='unsuccessful_result',
                     component=component, operation=operation, outcome='failed', duration_ms=elapsed)
            else:
                emit(service, 'operation.completed', level='WARNING' if elapsed >= 1000 else 'DEBUG',
                     component=component, operation=operation, outcome='completed', duration_ms=elapsed)
            return result

        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def wrapped(*args, **kwargs):
                started, token = start_span()
                try:
                    return result_value(await function(*args, **kwargs), started)
                except BaseException as exc:
                    failed(exc, started)
                    raise
                finally:
                    _CONTEXT.reset(token)
        else:
            @wraps(function)
            def wrapped(*args, **kwargs):
                started, token = start_span()
                try:
                    return result_value(function(*args, **kwargs), started)
                except BaseException as exc:
                    failed(exc, started)
                    raise
                finally:
                    _CONTEXT.reset(token)
        wrapped._gysam_observed = True
        return wrapped
    return decorate


def observe_class(cls, service):
    """Install once on methods owned by an application class, preserving descriptors."""
    import inspect
    with _CONFIG_LOCK:
        for name, value in list(vars(cls).items()):
            if name.startswith('_'):
                continue
            descriptor = type(value) if isinstance(value, (staticmethod, classmethod)) else None
            function = value.__func__ if descriptor else value
            if inspect.isfunction(function):
                wrapped = observe(service)(function)
                setattr(cls, name, descriptor(wrapped) if descriptor else wrapped)
    return cls


def instrument_module(namespace, service):
    """Instrument owned public services/functions; imported dependencies are untouched."""
    import inspect
    module = namespace.get('__name__')
    for name, value in list(namespace.items()):
        if name.startswith('_') or getattr(value, '__module__', None) != module:
            continue
        if inspect.isclass(value) and not issubclass(value, BaseException):
            observe_class(value, service)
        elif inspect.isfunction(value):
            namespace[name] = observe(service)(value)
