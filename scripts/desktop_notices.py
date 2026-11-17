"""Collect installed dependency notices without touching configuration or data."""
import json
from importlib.metadata import distribution, PackageNotFoundError
from pathlib import Path
import re
import sys

from scripts.audit_python_dependencies import dependencies
from scripts.dependency_inventory import javascript_entries


def collect(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    inventory = []
    notices = ['FIRE-COMMAND STUDIO / third-party notices',
               'The project owner has not selected a general public source license.',
               'Third-party code retains its own license. Build dependencies listed here are not necessarily shipped runtime code.', '']
    for name in dependencies(root) + ['pyinstaller', 'pyinstaller-hooks-contrib']:
        try:
            package = distribution(name)
        except PackageNotFoundError:
            continue
        metadata = package.metadata
        entry = {'ecosystem':'python','name':name,'version':package.version,
                 'license':metadata.get('License-Expression') or metadata.get('License') or 'See distribution notices'}
        inventory.append(entry)
        notices.extend(['=' * 72, f"{name} {package.version}", str(entry['license'])])
        for item in sorted(package.files or [], key=str):
            if not re.search(r'(?i)(?:license|copying|notice|copyright)', Path(str(item)).name):
                continue
            source = Path(package.locate_file(item))
            if source.is_file() and source.stat().st_size <= 1024 * 1024:
                try:
                    text = source.read_text(encoding='utf-8')
                except UnicodeError:
                    continue
                notices.extend([f'--- {item} ---', text])
    lock = json.loads((root / 'package-lock.json').read_text(encoding='utf-8'))
    for info in sorted(javascript_entries(lock), key=lambda entry: entry['path']):
        name = info['path']
        directory = root / name
        if info['first_party'] or not directory.is_dir():
            continue
        inventory.append({'ecosystem':'javascript','name':name.removeprefix('node_modules/'),'version':info['version'],'license':info['license_declaration'],'build_only':bool(info['development'])})
        for source in sorted(directory.iterdir()):
            if source.is_file() and re.match(r'(?i)^(license|copying|notice)(?:\.|$)', source.name) and source.stat().st_size < 1024 * 1024:
                notices.extend(['=' * 72, f"{name} {info.get('version')}", source.read_text(encoding='utf-8', errors='replace')])
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        notices.extend(['=' * 72, 'Python runtime / bundled components', python_license.read_text(encoding='utf-8', errors='replace')])
    (destination / 'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notices), encoding='utf-8')
    (destination / 'DEPENDENCY_INVENTORY.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return len(inventory)


if __name__ == '__main__':
    print(json.dumps({'notice_entries':collect(Path.cwd(), Path('runtime/desktop-notices'))}))
