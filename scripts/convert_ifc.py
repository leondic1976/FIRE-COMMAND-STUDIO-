"""Run only on an institution-approved offline conversion host; no HTTP worker."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.api.asset_scanner import LocalClamScanner
from apps.api.ifc_conversion import ConverterSettings,convert_ifc
from apps.api.safety import MAX_ASSET_BYTES


async def main(source,destination):
    source,destination=source.resolve(),destination.resolve()
    sidecar=destination.with_suffix(destination.suffix+'.conversion.json')
    if not source.is_file() or source.suffix.lower()!='.ifc' or source.stat().st_size>MAX_ASSET_BYTES:
        raise ValueError('15MiB 이하의 IFC 파일을 지정하세요.')
    if destination.suffix.lower()!='.glb' or destination.exists() or sidecar.exists():
        raise ValueError('존재하지 않는 새 GLB/기록 경로를 지정하세요.')
    content,metadata=await convert_ifc(source.read_bytes(),ConverterSettings.from_env(),LocalClamScanner())
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as output:output.write(content)
    try:
        with sidecar.open('x',encoding='utf-8') as output:json.dump(metadata,output,ensure_ascii=False,indent=2)
    except Exception:
        destination.unlink() # Only the new file created by this invocation.
        raise
    print(json.dumps({'output_bytes':len(content),'output_sha256':metadata['output_sha256'],'rights_review_required':True},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    try:asyncio.run(main(args.source,args.destination))
    except (ValueError,OSError) as error:raise SystemExit(str(error)) from None
