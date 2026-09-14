"""GYS-OBS-001: bounded diagnostic data; log content never becomes instructions."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re

NAME = re.compile(r'^[A-Za-z0-9._-]{1,96}$')
IDENTITY = re.compile(r'^[A-Za-z0-9._-]{1,64}$')
FINGERPRINT = re.compile(r'^[a-f0-9]{64}$')
FIELDS = frozenset(('service', 'event', 'level', 'run_id', 'request_id',
    'correlation_id', 'operation_id', 'job_id', 'worker_id', 'delivery_id',
    'ticket_id', 'evidence_id', 'component', 'operation', 'outcome', 'reason',
    'error_type', 'revision', 'method', 'span_id', 'parent_span_id', 'plan_id'))
NUMBERS = frozenset(('duration_ms', 'status_code', 'exit_code', 'attempt', 'count'))
SELECTORS = frozenset(('request_id', 'correlation_id', 'run_id', 'job_id',
    'operation_id', 'delivery_id', 'span_id', 'plan_id'))


def normalize(record):
    """Accept schema-v1 diagnostics and discard all non-contract data."""
    if not isinstance(record, dict) or type(record.get('schema_version')) is not int or record['schema_version'] != 1:
        raise ValueError('unsupported_diagnostic_schema')
    out = {'schema_version': 1}
    for key in FIELDS:
        value = record.get(key)
        if isinstance(value, str) and NAME.fullmatch(value):
            out[key] = value
    if not out.get('service') or not out.get('event') or out.get('level') not in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
        raise ValueError('invalid_diagnostic_identity')
    for key in NUMBERS:
        value = record.get(key)
        if type(value) in (int, float) and abs(value) < 10**16 and math.isfinite(value):
            out[key] = round(value, 3)
    timestamp = record.get('timestamp')
    if isinstance(timestamp, str) and len(timestamp) <= 40:
        try:
            parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            if parsed.tzinfo is not None:
                out['timestamp'] = parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            out.pop('timestamp', None)
    frames = record.get('error_frames')
    if isinstance(frames, list):
        clean = []
        for frame in frames[-8:]:
            if not isinstance(frame, dict):
                continue
            file, function, line = frame.get('file'), frame.get('function'), frame.get('line')
            if (isinstance(file, str) and NAME.fullmatch(file) and isinstance(function, str)
                    and NAME.fullmatch(function) and type(line) is int and 0 < line < 10**7):
                clean.append({'file': file, 'function': function, 'line': line})
        out['error_frames'] = clean
    return out


def signature(record):
    """Exact service/revision/code-family match; volatile IDs/line numbers excluded."""
    row = normalize(record)
    frame = (row.get('error_frames') or [{}])[-1]
    return {key: row.get(key, '') for key in ('service', 'revision', 'event', 'component', 'operation', 'error_type', 'reason', 'status_code', 'exit_code')} | {
        'file': frame.get('file', ''), 'function': frame.get('function', '')}


def fingerprint(record):
    return sha256(json.dumps(signature(record), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def is_failure(row):
    return (row['level'] in {'ERROR', 'CRITICAL'} or row.get('error_type') is not None
            or row.get('status_code', 0) >= 500 or row.get('exit_code', 0) != 0)


def analyze(records):
    if not isinstance(records, list) or len(records) > 200:
        raise ValueError('diagnostic_batch_limit')
    rows = [normalize(row) for row in records]
    groups = {}
    for row in rows:
        if not is_failure(row):
            continue
        key = fingerprint(row)
        item = groups.setdefault(key, {'fingerprint': key, 'signature': signature(row),
            'count': 0, 'sample': row, 'resolution': 'unclassified', 'verified_resolution_required': True})
        item['count'] += 1
        item['sample'] = row
    return {'status': 'failures_found' if groups else 'no_failure_in_window',
            'events': len(rows), 'services': dict(Counter(row['service'] for row in rows)),
            'failures': sorted(groups.values(), key=lambda x: (-x['count'], x['fingerprint'])),
            'timeline': rows, 'evidence_is_untrusted_data': True,
            'automatic_execution': False}


def telemetry(record):
    row = normalize(record)
    labels = {key: value for key, value in row.items() if key in FIELDS and key not in {'event', 'level'}}
    labels['severity'] = 'high' if is_failure(row) else 'info'
    labels['diagnostic_fingerprint'] = fingerprint(row)
    return {'kind': 'log', 'source': row['service'], 'name': row['event'],
            'value': row.get('duration_ms', 1), 'labels': labels,
            'timestamp': row.get('timestamp')}
