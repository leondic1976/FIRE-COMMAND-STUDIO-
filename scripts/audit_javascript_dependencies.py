"""Audit all npm dependencies; assess one time-limited build-only advisory."""
from datetime import date
import json
from pathlib import Path
import shutil
import subprocess

ADVISORY = 'https://github.com/advisories/GHSA-fc5q-39xc-vjpf'
REVIEW_BY = date(2026, 12, 18)


def assess(report, lock, today=None):
    if report.get('error'):
        raise ValueError('npm advisory lookup failed')
    findings = report.get('vulnerabilities', {})
    if not findings:
        return {'reported': 0, 'accepted_build_only': [], 'production_advisories': 0}
    # No fixed picomatch release exists as of 2026-11-18. Vite/Vitest only
    # process repository-owned build patterns. Node is absent at runtime.
    if (today or date.today()) > REVIEW_BY:
        raise ValueError('Build-only advisory assessment expired')
    for name, finding in findings.items():
        nodes = finding.get('nodes', [])
        if not nodes or any(lock['packages'].get(node, {}).get('dev') is not True for node in nodes):
            raise ValueError('Vulnerable dependency is not exclusively a development tool')
        for cause in finding.get('via', []):
            if isinstance(cause, str):
                if cause not in findings:
                    raise ValueError('Unknown indirect advisory')
            elif cause.get('url') != ADVISORY or cause.get('name') != 'picomatch':
                raise ValueError('Unassessed JavaScript advisory')
        if name not in {'picomatch', 'fdir', 'tinyglobby', 'vite', 'vitest'}:
            raise ValueError('Unassessed dependency path')
    direct = findings.get('picomatch', {})
    if not any(isinstance(item, dict) and item.get('url') == ADVISORY for item in direct.get('via', [])):
        raise ValueError('Expected advisory root missing')
    if any(lock['packages'][node].get('version') != '4.0.7' for node in direct['nodes']):
        raise ValueError('Reassess the changed picomatch version')
    return {'reported': len(findings), 'accepted_build_only': [ADVISORY],
            'production_advisories': 0, 'review_by': REVIEW_BY.isoformat(),
            'reason': 'Build-only repository patterns; no Node/build server in deployed runtime; no upstream patched version.'}


def main():
    npm = shutil.which('npm.cmd') or shutil.which('npm')
    result = subprocess.run([npm, 'audit', '--json'], capture_output=True, text=True, encoding='utf-8', timeout=90)
    if result.returncode not in (0, 1):
        raise SystemExit('npm advisory lookup failed')
    try:
        report = json.loads(result.stdout)
        verdict = assess(report, json.loads(Path('package-lock.json').read_text(encoding='utf-8')))
    except (ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error)) from None
    destination = Path('artifacts/javascript-advisories.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({'assessment': verdict, 'npm_report': report}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(verdict))


if __name__ == '__main__':
    main()
