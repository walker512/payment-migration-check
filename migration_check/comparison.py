"""Review-only rescan differences. Absence is never a migration verdict."""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
import stat
from .core import RULES

MAX_BASELINE = 16 * 1024 * 1024
COVERAGE_KEYS = ('files_read', 'bytes_read', 'excluded_entries', 'unsupported_files',
                 'symlinks_skipped', 'unreadable_files', 'oversize_files', 'binary_files', 'non_utf8_files')
INCOMPLETE_KEYS = ('unreadable_files', 'oversize_files', 'binary_files', 'non_utf8_files')
LABELS = {rule: label for rule, label, _ in RULES}


def incomplete(report: dict) -> bool:
    return report['truncated'] or any(report['coverage'][key] for key in INCOMPLETE_KEYS)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate baseline JSON key')
        result[key] = value
    return result


def _read(path: Path) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Baseline must be a regular non-symlink JSON file')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        actual = os.fstat(stream.fileno())
        if not stat.S_ISREG(actual.st_mode) or (before.st_dev, before.st_ino) != (actual.st_dev, actual.st_ino):
            raise ValueError('Baseline file changed while opening')
        raw = stream.read(MAX_BASELINE + 1)
    if len(raw) > MAX_BASELINE:
        raise ValueError('Baseline exceeds 16 MiB limit')
    return raw


def compare(report: dict, path: Path) -> dict:
    raw = _read(path)
    old = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid baseline number')))
    if not isinstance(old, dict) or type(old.get('schema_version')) is not int or old['schema_version'] != 1:
        raise ValueError('Baseline must be a schema_version 1 report')
    if not isinstance(old.get('privacy'), dict) or type(old['privacy'].get('paths_pseudonymized')) is not bool:
        raise ValueError('Baseline must include boolean path privacy metadata')
    if old['privacy']['paths_pseudonymized'] != report['privacy']['paths_pseudonymized']:
        raise ValueError('Baseline path privacy mode must match this scan')
    if old.get('ruleset_fingerprint') != report['ruleset_fingerprint']:
        raise ValueError('Baseline rules or scan policy differ; review and regenerate baseline')
    if not report.get('scope_id') or old.get('scope_id') != report['scope_id']:
        raise ValueError('Baseline scope differs or is missing; use the same explicit --scope-id for the same relative scan root')
    coverage = old.get('coverage')
    if not isinstance(coverage, dict) or set(coverage) != set(COVERAGE_KEYS) or any(type(v) is not int or not 0 <= v <= 2**63-1 for v in coverage.values()) or type(old.get('truncated')) is not bool:
        raise ValueError('Malformed baseline coverage')
    findings = old.get('findings')
    if not isinstance(findings, list) or len(findings) > 60000:
        raise ValueError('Malformed baseline findings')
    previous = {}
    for item in findings:
        if (not isinstance(item, dict) or not isinstance(item.get('rule'), str) or item['rule'] not in LABELS
                or not isinstance(item.get('file'), str) or not item['file'] or len(item['file']) > 32768
                or type(item.get('line')) is not int or not 1 <= item['line'] <= 524289):
            raise ValueError('Malformed baseline finding')
        if report['privacy']['paths_pseudonymized'] and not re.fullmatch(r'file-[0-9a-f]{12}', item['file']):
            raise ValueError('Malformed pseudonymized baseline path')
        key = (item['rule'], item['file'])
        if key in previous:
            raise ValueError('Duplicate baseline finding')
        # Never re-export arbitrary baseline labels, excerpts or extra fields.
        previous[key] = {'rule': item['rule'], 'label': LABELS[item['rule']], 'file': item['file'], 'line': item['line']}
    current = {(f['rule'], f['file']): f for f in report['findings']}
    return {
        'comparison_version': 1,
        'baseline_sha256': hashlib.sha256(raw).hexdigest(),
        'new': [current[k] for k in sorted(current.keys() - previous.keys())],
        'retained': [dict(current[k], previous_line=previous[k]['line']) for k in sorted(current.keys() & previous.keys())],
        'not_observed_now': [previous[k] for k in sorted(previous.keys() - current.keys())],
        'baseline_incomplete': bool(incomplete(old)),
        'current_incomplete': bool(incomplete(report)),
        'coverage_changes': {k: {'before': coverage[k], 'after': report['coverage'][k], 'delta': report['coverage'][k] - coverage[k]} for k in COVERAGE_KEYS},
        'note': 'Not observed now is not resolved or migrated: deletion, renaming, exclusions, unreadable source or heuristic misses can hide usage. Counts do not prove the same files were assessed. Baseline bytes and scope labels are not authenticated. Review both scans and local changes.',
    }
