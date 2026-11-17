"""Prepare fixed FFmpeg 9.0.2 Windows tools; never enable media processing.

The upstream FFmpeg download page lists Gyan Windows builds. Preserve the
downloaded archive, its GPL/source notices, origin and SHA256 in runtime only.
"""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import zipfile
import httpx

VERSION='9.0.2'
URL='https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip'
SHA256='60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
PREFIX='ffmpeg-9.0.2-essentials_build'


def prepare(destination):
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    archive=destination/'official-windows.zip'
    if not archive.exists():
        try:
            with httpx.Client(follow_redirects=True,timeout=60,trust_env=False) as client,client.stream('GET',URL) as response:
                if response.status_code!=200 or not(response.url.host=='github.com' or response.url.host.endswith('.githubusercontent.com')):raise ValueError('공식 도구 다운로드 응답 오류')
                size=0
                with archive.open('xb') as output:
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>200*1024*1024:raise ValueError('도구 다운로드 크기 제한 초과')
                        output.write(chunk)
        except httpx.HTTPError:raise ValueError('고정 FFmpeg 도구 다운로드 실패') from None
    if archive.stat().st_size>200*1024*1024 or hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:raise ValueError('고정 FFmpeg ZIP 해시 불일치. 실행하지 마세요.')
    hashes={}
    with zipfile.ZipFile(archive) as zipped:
        entries=zipped.infolist()
        if len(entries)>2000 or sum(item.file_size for item in entries)>800*1024*1024:raise ValueError('도구 압축 해제 예산 초과')
        for name in ['ffmpeg.exe','ffprobe.exe']:
            path=destination/name;entry=zipped.getinfo(PREFIX+'/bin/'+name)
            if PurePosixPath(entry.filename).parts!=(PREFIX,'bin',name) or entry.file_size>350*1024*1024 or entry.file_size>max(100000,entry.compress_size*100):raise ValueError('도구 압축 경로/크기 오류')
            data=zipped.read(entry);hashes[name]=hashlib.sha256(data).hexdigest()
            if path.is_symlink():raise ValueError('도구 대상 심볼릭 링크 차단')
            if path.exists():
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=hashes[name]:raise ValueError('기존 도구와 고정 배포본이 다릅니다.')
            else:
                with path.open('xb') as output:output.write(data)
    actual={path.name for path in destination.iterdir() if path.suffix.lower() in ['.exe','.dll']}
    if actual!=set(hashes):raise ValueError('도구 디렉터리의 추가 실행파일/DLL 차단')
    result={'version':VERSION,'source_url':URL,'archive_sha256':SHA256,'license':'GPL-3.0-or-later; preserve full archive/source notices before redistribution','source_commit':'https://github.com/FFmpeg/FFmpeg/commit/946fcce07b','files':hashes,'institutional_approval':False}
    manifest=destination/'bundle.json';encoded=(json.dumps(result,indent=2)+'\n').encode()
    if manifest.exists():
        if manifest.read_bytes()!=encoded:raise ValueError('기존 매니페스트와 다릅니다. 새 디렉터리를 사용하세요.')
    else:
        with manifest.open('xb') as output:output.write(encoded)
    return {'manifest':str(manifest),'manifest_sha256':hashlib.sha256(encoded).hexdigest(),'files':len(hashes),'institutional_approval':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    try:print(json.dumps(prepare(parser.parse_args().destination),ensure_ascii=False,indent=2))
    except (OSError,ValueError,KeyError,zipfile.BadZipFile) as error:raise SystemExit(str(error)) from None
