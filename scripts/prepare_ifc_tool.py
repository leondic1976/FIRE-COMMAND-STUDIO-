"""Prepare a pinned official Windows IfcConvert bundle, without enabling it.

No administrator changes, arbitrary URL, runtime execution or institutional
approval. The archive checksum is published by the upstream GitHub release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import httpx

URL='https://github.com/IfcOpenShell/IfcOpenShell/releases/download/ifcconvert-0.8.5/ifcconvert-0.8.5-win64.zip'
SHA256='36e9a527f57c0894138cf7df29d299c378d90bcbf468abf93a59e32c9d89cd48'


def prepare(destination):
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    archive=destination/'official-win64.zip'
    if not archive.exists():
        try:
            with httpx.Client(follow_redirects=True,timeout=60,trust_env=False) as client,client.stream('GET',URL) as response:
                if response.status_code!=200 or not (response.url.host=='github.com' or response.url.host.endswith('.githubusercontent.com')):
                    raise ValueError('공식 변환 도구 다운로드 응답을 확인할 수 없습니다.')
                size=0
                with archive.open('xb') as target:
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>150*1024*1024:raise ValueError('다운로드 크기 제한 초과')
                        target.write(chunk)
        except httpx.HTTPError:raise ValueError('공식 변환 도구 다운로드에 실패했습니다.') from None
    if archive.stat().st_size>150*1024*1024 or hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:
        raise ValueError('공식 배포 ZIP 해시가 다릅니다. 실행하지 마세요.')
    with zipfile.ZipFile(archive) as zipped:
        entries=zipped.infolist()
        if len(entries)>100 or sum(entry.file_size for entry in entries)>500*1024*1024:raise ValueError('도구 압축 해제 한도 초과')
        expected={}
        for entry in entries:
            name=Path(entry.filename).name
            if name!=entry.filename or ':' in name or '\\' in name or entry.file_size>max(100000,entry.compress_size*100):raise ValueError('도구 ZIP 경로/압축 비율 오류')
            if not name.lower().endswith(('.dll','.exe')):continue
            content=zipped.read(entry);expected[name]=hashlib.sha256(content).hexdigest();path=destination/name
            if path.is_symlink():raise ValueError('도구 대상에 심볼릭 링크가 있습니다.')
            if path.exists():
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected[name]:raise ValueError('기존 도구 파일이 공식 배포본과 다릅니다.')
            else:
                with path.open('xb') as output:output.write(content)
    actual={p.name for p in destination.iterdir() if p.suffix.lower() in ['.dll','.exe']}
    if actual!=set(expected) or 'IfcConvert.exe' not in expected:raise ValueError('추가 실행파일/DLL이 있는 디렉터리는 사용할 수 없습니다.')
    metadata={'source_url':URL,'official_archive_sha256':SHA256,'files':expected,'institutional_approval':False}
    manifest=destination/'bundle.json'
    encoded=(json.dumps(metadata,indent=2)+'\n').encode()
    if manifest.exists():
        if manifest.read_bytes()!=encoded:raise ValueError('기존 도구 매니페스트가 다릅니다. 새 디렉터리를 사용하세요.')
    else:
        with manifest.open('xb') as output:output.write(encoded)
    return {'manifest':str(manifest),'manifest_sha256':hashlib.sha256(encoded).hexdigest(),'files':len(expected),'institutional_approval':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    try:print(json.dumps(prepare(parser.parse_args().destination),ensure_ascii=False,indent=2))
    except (ValueError,OSError,zipfile.BadZipFile) as error:raise SystemExit(str(error)) from None
