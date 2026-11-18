from copy import deepcopy
from datetime import date

import pytest

from scripts.audit_javascript_dependencies import ADVISORY, assess


def fixture():
    return ({'vulnerabilities': {'picomatch': {'nodes': ['node_modules/picomatch'],
        'via': [{'url': ADVISORY, 'name': 'picomatch'}]}}},
        {'packages': {'node_modules/picomatch': {'dev': True, 'version': '4.0.7'}}})


def test_current_build_only_advisory_and_clean_result():
    report, lock = fixture()
    assert assess(report, lock, date(2026, 11, 18))['accepted_build_only'] == [ADVISORY]
    assert assess({'vulnerabilities': {}}, lock)['reported'] == 0


@pytest.mark.parametrize('kind', ['production', 'unknown', 'expired', 'new-version', 'lookup-error'])
def test_unassessed_or_production_findings_fail(kind):
    report, lock = deepcopy(fixture())
    today = date(2026, 11, 18)
    if kind == 'production':
        lock['packages']['node_modules/picomatch']['dev'] = False
    elif kind == 'unknown':
        report['vulnerabilities']['picomatch']['via'].append({'url': 'https://example.invalid/new'})
    elif kind == 'expired':
        today = date(2026, 12, 19)
    elif kind == 'new-version':
        lock['packages']['node_modules/picomatch']['version'] = '4.0.8'
    else:
        report['error'] = {'code': 'ENOTFOUND'}
    with pytest.raises(ValueError):
        assess(report, lock, today)
