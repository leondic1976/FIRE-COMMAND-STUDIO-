import json
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.api.domain import Exercise
from apps.api.asset_contracts import AssetProvenance
from apps.api.application import create_app
from apps.api.seeds import base_roles, demo_exercise


def export():
    root = Path(__file__).resolve().parents[1]
    folder = root / 'packages' / 'domain-schemas'
    app = create_app('sqlite:///:memory:', demo_mode=True)
    manifest = []

    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        path.write_bytes(content)
        manifest.append({'path': path.relative_to(root).as_posix(), 'sha256': hashlib.sha256(content).hexdigest()})

    try:
        write(folder / 'exercise.schema.json', Exercise.model_json_schema())
        write(folder / 'asset-provenance.schema.json', AssetProvenance.model_json_schema())
        write(folder / 'openapi.json', app.openapi())
        write(root / 'data' / 'role-seeds' / 'statutory-base.json', [r.model_dump(mode='json') for r in base_roles()])
        for template in ['factory', 'highrise', 'underground', 'compound']:
            exercise = demo_exercise('example-' + template, template)
            write(root / 'data' / 'synthetic' / (template + '.json'), exercise.model_dump(mode='json'))
        write(root / 'data' / 'manifest.json', {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'synthetic_only': True,
            'institutional_approval': False,
            'note': '합성 개발 예시. 날짜는 생성 시점 기준이며 실제 명부·현장자료가 아님. 발행 전 숙지/검수 필요.',
            'files': manifest.copy(),
        })
        print(f'Exported contracts and synthetic examples ({len(manifest)} files).')
    finally:
        app.state.store.engine.dispose()


if __name__ == '__main__':
    export()
