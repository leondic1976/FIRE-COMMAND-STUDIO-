"""Bounded approved MP4/WebM normalization. Caller must first obtain AV CLEAN.

No user URL, process argument or external media protocol is accepted. Windows
Job limits are resource controls; institution host isolation is still required.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from fractions import Fraction
from pydantic import Field
from .asset_validation import AssetValidationError
from .domain import Contract,AssetManifest
from .offline_process import WorkerError,private_work_directory,run_bounded
from .safety import MAX_ASSET_BYTES


class MediaUnavailable(AssetValidationError):pass


class MediaSettings(Contract):
    approved: bool=False
    approval_reference: str=Field(default='',max_length=200)
    host_isolation_confirmed: bool=False
    manifest_path: str=''
    manifest_sha256: str=Field(default='',pattern=r'^(?:[a-f0-9]{64})?$')
    timeout_seconds: float=Field(default=60,ge=.05,le=120)

    @classmethod
    def from_env(cls):
        return cls(approved=os.getenv('MEDIA_PROCESSING_APPROVED')=='true',approval_reference=os.getenv('MEDIA_PROCESSING_APPROVAL_REF',''),
            host_isolation_confirmed=os.getenv('MEDIA_HOST_ISOLATION_CONFIRMED')=='true',manifest_path=os.getenv('MEDIA_TOOL_MANIFEST',''),manifest_sha256=os.getenv('MEDIA_TOOL_MANIFEST_SHA256',''))


class MediaProcessor:
    def __init__(self,settings=None):self.settings=settings or MediaSettings.from_env()

    def status(self):
        ready=bool(self.settings.approved and self.settings.approval_reference.strip() and self.settings.host_isolation_confirmed and self.settings.manifest_path and self.settings.manifest_sha256)
        return {'configured':ready,'reason':'승인된 영상 변환 도구·호스트 격리·실제 AV 검증이 필요합니다.','real_host_or_av_verified':False}

    def _tools(self):
        try:return self._validated_tools()
        except MediaUnavailable:raise
        except (OSError,TypeError,ValueError):raise MediaUnavailable('영상 도구 설정/접근/매니페스트 계약 오류') from None

    def _validated_tools(self):
        if not self.status()['configured']:raise MediaUnavailable('승인 영상 도구/호스트 미설정. 격리를 유지합니다.')
        path=Path(self.settings.manifest_path).resolve()
        if not path.is_file() or path.stat().st_size>65536 or hashlib.sha256(path.read_bytes()).hexdigest()!=self.settings.manifest_sha256:raise MediaUnavailable('영상 도구 매니페스트 무결성 오류')
        try:manifest=json.loads(path.read_text(encoding='utf-8'));files=manifest['files']
        except (ValueError,KeyError,UnicodeError):raise MediaUnavailable('영상 도구 매니페스트 계약 오류') from None
        if manifest.get('version')!='9.0.2' or not isinstance(files,dict) or set(files)!= {'ffmpeg.exe','ffprobe.exe'}:raise MediaUnavailable('고정 영상 도구 구성이 아닙니다.')
        actual={item.name for item in path.parent.iterdir() if item.suffix.lower() in ['.exe','.dll']}
        if actual!=set(files):raise MediaUnavailable('추가 실행파일/DLL이 있는 영상 도구는 실행하지 않습니다.')
        for name,expected in files.items():
            item=path.parent/name
            if item.is_symlink() or not item.is_file() or item.stat().st_size>350*1024*1024 or hashlib.sha256(item.read_bytes()).hexdigest()!=expected:raise MediaUnavailable('영상 도구 파일 무결성 오류')
        return path.parent/'ffmpeg.exe',path.parent/'ffprobe.exe'

    @staticmethod
    def _info(data,max_duration=180):
        try:
            info=json.loads(data);streams=info['streams'];videos=[stream for stream in streams if stream['codec_type']=='video'];audios=[stream for stream in streams if stream['codec_type']=='audio']
            if len(streams)>4 or len(videos)!=1 or len(audios)>1 or any(stream['codec_type'] not in ['video','audio'] for stream in streams):raise ValueError()
            video=videos[0];duration=float(info['format']['duration']);fps=float(Fraction(video['avg_frame_rate']));width=int(video['width']);height=int(video['height'])
            if not math.isfinite(duration) or not 0<duration<=max_duration or not 0<fps<=60 or not 16<=width<=4096 or not 16<=height<=4096:raise ValueError()
            copyright_notice=str(info['format'].get('tags',{}).get('copyright',''))[:500]
            return duration,fps,width,height,bool(audios),copyright_notice,video['codec_name']
        except (ValueError,TypeError,KeyError,IndexError,ZeroDivisionError,OverflowError):raise AssetValidationError('영상은180초·4096px·60fps 이하의 영상1/음성1 트랙이어야 합니다. 오프라인에서 클립을 준비하세요.') from None

    def normalize(self,data):
        if not data or len(data)>MAX_ASSET_BYTES:raise AssetValidationError('영상은15MiB 이하의 파일이어야 합니다.')
        mp4=len(data)>=12 and data[4:8]==b'ftyp'
        if not mp4 and not data.startswith(b'\x1a\x45\xdf\xa3'):raise AssetValidationError('실제 MP4/WebM 파일만 입력하세요.')
        ffmpeg,ffprobe=self._tools();parent=Path(tempfile.gettempdir()).resolve()
        with tempfile.TemporaryDirectory(prefix='fcs-media-',dir=parent) as directory:
            work=Path(directory).resolve()
            if work.parent!=parent or not work.name.startswith('fcs-media-'):raise MediaUnavailable('영상 임시 경로 오류')
            try:private_work_directory(work)
            except WorkerError:raise MediaUnavailable('영상 비공개 작업 디렉터리 권한 적용 실패') from None
            source=work/('source.mp4' if mp4 else 'source.webm');output=work/'normalized.webm';source.write_bytes(data)
            options=['-protocol_whitelist','file','-format_whitelist','mov,matroska,webm']+(['-enable_drefs','0','-use_absolute_path','0'] if mp4 else [])
            probe=['-v','error',*options,'-show_entries','stream=codec_type,codec_name,width,height,avg_frame_rate:format=duration:format_tags=copyright','-of','json']
            try:
                raw=run_bounded([str(ffprobe),*probe,str(source)],work,seconds=min(15,self.settings.timeout_seconds))
                duration,fps,width,height,has_audio,copyright_notice,codec=self._info(raw)
                if codec not in ['h264','hevc','vp8','vp9','av1']:raise AssetValidationError('지원 영상 코덱이 아닙니다. H264/HEVC/VP8/VP9/AV1 클립을 준비하세요.')
                args=[str(ffmpeg),'-hide_banner','-loglevel','error','-nostdin',*options,'-i',str(source),'-map','0:v:0','-map','0:a:0?','-map_metadata','-1','-map_metadata:s','-1','-map_chapters','-1','-sn','-dn',
                    '-vf',"scale=w='min(960,iw)':h='min(540,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",'-r','20','-pix_fmt','yuv420p','-c:v','libvpx','-deadline','realtime','-cpu-used','8','-threads','1','-b:v','500k','-maxrate','650k','-bufsize','1M',
                    '-c:a','libopus','-b:a','48k','-f','webm','-n',str(output)]
                run_bounded(args,work,seconds=self.settings.timeout_seconds,output=output,max_output=MAX_ASSET_BYTES)
                canonical=output.read_bytes()
                checked=run_bounded([str(ffprobe),'-v','error','-protocol_whitelist','file','-format_whitelist','matroska,webm','-show_entries','stream=codec_type,codec_name,width,height,avg_frame_rate:format=duration:format_tags=copyright','-of','json',str(output)],work,seconds=min(15,self.settings.timeout_seconds))
                # Opus codec padding can add milliseconds to the container.
                out_duration,out_fps,out_width,out_height,out_audio,_,out_codec=self._info(checked,max_duration=180.25)
                if abs(out_duration-duration)>1 or out_codec!='vp8' or out_width>960 or out_height>540 or out_fps>20.1 or out_audio!=has_audio:raise AssetValidationError('정규화 영상 검증 불일치')
            except WorkerError:raise AssetValidationError('영상 파서/변환 오류·작업 예산 초과. 승인된 오프라인 클립을 준비하세요.') from None
            return canonical,AssetManifest(width=out_width,height=out_height,duration_seconds=out_duration,frame_rate=out_fps,has_audio=out_audio,video_codec='vp8',copyright_notice=copyright_notice,processing_tool='FFmpeg 9.0.2',processing_manifest_sha256=self.settings.manifest_sha256)
