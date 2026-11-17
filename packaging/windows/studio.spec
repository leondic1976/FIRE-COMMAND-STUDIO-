# Build from repository root with: python -m PyInstaller packaging/windows/studio.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

root = Path(SPECPATH).resolve().parents[1]
datas = [(str(root / 'dist'), 'dist')]
notices = root / 'runtime' / 'desktop-notices'
if not (notices / 'THIRD_PARTY_NOTICES.txt').is_file():
    raise ValueError('Generate dependency notices before packaging.')
datas.append((str(notices), 'notices'))
for distribution in ['fastapi','starlette','pydantic','SQLAlchemy','uvicorn','python-multipart','Pillow']:
    datas += copy_metadata(distribution)
hidden = collect_submodules('uvicorn') + collect_submodules('sqlalchemy.dialects.sqlite') + collect_submodules('websockets')
a = Analysis([str(root / 'apps' / 'desktop' / 'main.py')], pathex=[str(root)], binaries=[], datas=datas,
             hiddenimports=hidden, hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['pytest','pytest_asyncio','PyMuPDF','fitz','playwright','psycopg2','uvloop','numpy','pandas','scipy','matplotlib','IPython','torch','tensorflow','trio'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FIRECommandStudio', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=True, argv_emulation=False,
          version=str(root / 'packaging' / 'windows' / 'version_info.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FIRECommandStudio')
