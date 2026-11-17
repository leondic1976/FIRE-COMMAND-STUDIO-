"""Record installed direct Python and lockfile JavaScript license declarations.

This is an inventory, not a vulnerability scanner or a license approval engine.
No network requests or credentials are used.
"""
import argparse
import json
import platform
import re
from datetime import datetime, timezone
from importlib.metadata import metadata, version
from pathlib import Path


def inventory(root: Path):
    manifest = json.loads((root / 'package-lock.json').read_text(encoding='utf-8'))
    javascript = []
    for path, package in manifest['packages'].items():
        if not path:
            continue
        javascript.append({
            'path': path,
            'version': package['version'],
            'license_declaration': package.get('license', 'UNDECLARED'),
            'development': package.get('dev', False),
        })
    python = []
    for line in (root / 'requirements.txt').read_text(encoding='utf-8').splitlines():
        match = re.match(r'^([a-zA-Z0-9_.-]+)(?:\[[^]]+\])?==([^\s]+)$', line.strip())
        if not match:
            if line.strip() and not line.lstrip().startswith('#'):
                raise ValueError('Unsupported requirement declaration')
            continue
        name, expected = match.groups()
        installed = version(name)
        if installed != expected:
            raise ValueError(f'{name}: expected {expected}, installed {installed}')
        data = metadata(name)
        classifiers = [value for value in data.get_all('Classifier', []) if value.startswith('License ::')]
        python.append({
            'name': name, 'version': installed,
            'license_declaration': data.get('License-Expression') or data.get('License') or classifiers or 'UNDECLARED',
        })
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'platform': platform.system(),
        'scope': 'JavaScript lockfile entries; direct Python requirements installed in this environment',
        'institutional_license_approval': False,
        'javascript': javascript, 'python': python,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('artifacts/dependency-inventory.json'))
    args = parser.parse_args()
    result = inventory(Path(__file__).resolve().parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Recorded {len(result['javascript'])} JavaScript and {len(result['python'])} direct Python declarations.")
