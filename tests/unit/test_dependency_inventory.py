import pytest

from scripts.dependency_inventory import javascript_entries


def test_workspace_link_uses_declared_version_without_inventing_a_license():
    records = javascript_entries({'packages': {
        '': {'version': '0.1.0'},
        'node_modules/library': {'version': '1.2.3', 'license': 'MIT'},
        'node_modules/@studio/web': {'link': True, 'resolved': 'web'},
        'web': {'version': '0.1.0'},
    }})
    library, link, source = records
    assert library['version'] == '1.2.3' and not library['first_party']
    assert link['version'] == source['version'] == '0.1.0'
    assert link['license_declaration'] == source['license_declaration'] == 'UNDECLARED'
    assert link['first_party'] and source['first_party']


@pytest.mark.parametrize('package,others', [
    ({'link': True, 'resolved': '../outside'}, {'../outside': {'version': '1'}}),
    ({'link': True, 'resolved': 'missing'}, {}),
    ({'link': True, 'resolved': 'other'}, {'other': {'link': True, 'resolved': 'node_modules/example'}}),
    ({'license': 'MIT'}, {}),
])
def test_invalid_metadata_never_silently_omits_an_unversioned_dependency(package, others):
    with pytest.raises(ValueError):
        javascript_entries({'packages': {'node_modules/example': package, **others}})
