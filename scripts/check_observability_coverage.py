#!/usr/bin/env python3
"""Reviewable source inventory and provenance gate for GYS-OBS-001.

This checks that new source files receive an explicit boundary classification.
It is not a statement-coverage metric or proof that every function emits a log.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/observability-coverage.json'
MANIFEST = ROOT / 'docs/OBSERVABILITY_COVERAGE.json'
PROVENANCE = ROOT / 'config/observability-provenance.json'
EXTENSIONS = {'.py', '.js', '.jsx', '.cjs', '.mjs', '.ts', '.tsx', '.kt', '.java', '.sh', '.tf'}


def inventory(config):
    files = {}
    for scope in config['scopes']:
        folder = ROOT / scope['root']
        if not folder.exists():
            raise ValueError('missing_scope:' + scope['root'])
        for path in folder.rglob('*'):
            if not path.is_file() or path.is_symlink():
                continue
            name = path.relative_to(ROOT).as_posix()
            if any(part in {'__pycache__', 'node_modules', '.git', '.venv', 'tests', 'test'} for part in path.relative_to(folder).parts):
                continue
            if path.suffix not in EXTENSIONS and not (scope['root'] == 'scripts' and not path.suffix):
                continue
            source = path.read_text(encoding='utf-8')
            markers = [marker for marker in config['markers'] if marker in source]
            files[name] = {'boundary': scope['boundary'], 'direct_markers': markers}
    return {'schema_version': 1, 'feature': 'GYS-OBS-001', 'product': config['product'],
            'measurement': 'source inventory; boundary classifications require review, not statement coverage',
            'excluded': config['excluded'], 'files': dict(sorted(files.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Regenerate the inventory for code review')
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    actual = inventory(config)
    if args.write:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(actual, indent=2) + '\n')
    elif json.loads(MANIFEST.read_text()) != actual:
        raise SystemExit('Source inventory changed. Review the boundary and run scripts/check_observability_coverage.py --write.')
    provenance = json.loads(PROVENANCE.read_text())
    for name, expected in provenance['sha256'].items():
        if sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise SystemExit('Diagnostic source provenance mismatch: ' + name)
    for name, marker in config.get('required_boundaries', {}).items():
        if marker not in (ROOT / name).read_text():
            raise SystemExit('Required diagnostic boundary missing: ' + name)
    print(json.dumps({'feature': 'GYS-OBS-001', 'product': config['product'],
                      'source_files': len(actual['files']), 'provenance': 'matched', 'status': 'passed'}))


if __name__ == '__main__':
    main()
