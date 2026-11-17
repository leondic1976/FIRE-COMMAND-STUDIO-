"""Approved offline IFC→core GLB pipeline. Never called by the HTTP server."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from pydantic import Field
from .asset_validation import AssetValidationError,validate_model
from .domain import Contract,utcnow
from .offline_process import WorkerError,private_work_directory,run_bounded
from .safety import MAX_ASSET_BYTES


class ConversionError(ValueError):pass


class ConverterSettings(Contract):
    approved: bool=False
    approval_reference: str=Field(default='',max_length=200)
    offline_host_confirmed: bool=False
    manifest_path: str=''
    manifest_sha256: str=Field(default='',pattern=r'^(?:[a-f0-9]{64})?$')
    timeout_seconds: float=Field(default=60,ge=.05,le=120)

    @classmethod
    def from_env(cls):
        return cls(approved=os.getenv('IFC_CONVERSION_APPROVED')=='true',approval_reference=os.getenv('IFC_CONVERSION_APPROVAL_REF',''),
                   offline_host_confirmed=os.getenv('IFC_OFFLINE_HOST_CONFIRMED')=='true',manifest_path=os.getenv('IFC_TOOL_MANIFEST',''),manifest_sha256=os.getenv('IFC_TOOL_MANIFEST_SHA256',''))


def _tool(settings):
    if not (settings.approved and settings.approval_reference.strip() and settings.offline_host_confirmed and settings.manifest_path and settings.manifest_sha256):
        raise ConversionError('승인된 오프라인 작업기·변환 도구/해시 설정 전에는 IFC를 실행하지 않습니다.')
    path=Path(settings.manifest_path).resolve()
    if not path.is_file() or path.stat().st_size>65536 or hashlib.sha256(path.read_bytes()).hexdigest()!=settings.manifest_sha256:
        raise ConversionError('변환 도구 매니페스트 해시가 다릅니다.')
    try:manifest=json.loads(path.read_text(encoding='utf-8'));files=manifest['files']
    except (ValueError,KeyError,UnicodeError):raise ConversionError('변환 도구 매니페스트 오류') from None
    if not isinstance(files,dict) or not 1<=len(files)<=100 or 'IfcConvert.exe' not in files:raise ConversionError('승인된 IfcConvert 도구 구성이 아닙니다.')
    actual={item.name for item in path.parent.iterdir() if item.suffix.lower() in ['.exe','.dll']}
    if actual!=set(files):raise ConversionError('도구 디렉터리에 승인되지 않은 실행파일/DLL이 있습니다.')
    for name,expected in files.items():
        if not isinstance(name,str) or '/' in name or '\\' in name or ':' in name or not name.lower().endswith(('.exe','.dll')) or not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected):
            raise ConversionError('도구 파일·해시 계약 오류')
        item=path.parent/name
        if item.is_symlink() or not item.is_file() or item.stat().st_size>500*1024*1024 or hashlib.sha256(item.read_bytes()).hexdigest()!=expected:
            raise ConversionError('변환 도구 파일 무결성 오류')
    return path.parent/'IfcConvert.exe'


def validate_ifc(data):
    if not data or len(data)>MAX_ASSET_BYTES:raise ConversionError('IFC는15MiB 이하의 STEP 텍스트여야 합니다.')
    try:text=data.decode('utf-8-sig').strip()
    except UnicodeError:raise ConversionError('UTF-8/STEP IFC만 지원합니다. ZIP/XML은 오프라인에서 별도로 검토하세요.') from None
    if not text.startswith('ISO-10303-21;') or not text.endswith('END-ISO-10303-21;') or not re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'IFC(?:2X3|4|4X3_ADD2)'",text,re.I):
        raise ConversionError('IFC2X3/IFC4/IFC4X3_ADD2 STEP 헤더가 필요합니다.')
    if re.search(r'(?:https?://|file:|ftp:|\\\\|\.\.[/\\]|[a-z]:[/\\]|IFCEXTERNALLYDEFINED)',text,re.I) or '\0' in text:
        raise ConversionError('외부 URL·파일 참조가 있는 IFC는 자동 변환하지 않습니다.')


async def convert_ifc(data,settings,scanner):
    validate_ifc(data);tool=_tool(settings)
    scan=await scanner.scan(data)
    if scan.status!='CLEAN':raise ConversionError('원본 IFC 악성코드 검사를 통과하지 못했습니다.')
    # Fixed temporary paths, checked before recursive context cleanup. Binary
    # and DLLs stay in the pinned read-only tool bundle; cwd has only our data.
    parent=Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix='fcs-ifc-',dir=parent) as directory:
        work=Path(directory).resolve()
        if work.parent!=parent or not work.name.startswith('fcs-ifc-'):raise ConversionError('변환 임시 경로 오류')
        try:private_work_directory(work)
        except WorkerError as error:raise ConversionError(str(error)) from None
        source=work/'source.ifc';output=work/'converted.glb';source.write_bytes(data)
        try:
            version_bytes=run_bounded([str(tool),'--version'],work,seconds=min(10,settings.timeout_seconds))
            version=version_bytes.decode('utf-16-le' if b'\0' in version_bytes else 'utf-8',errors='replace').strip()
            if not re.fullmatch(r'IfcOpenShell IfcConvert [A-Za-z0-9.()+ _-]{1,120}',version):raise ConversionError('변환기 버전 응답을 확인하지 못했습니다.')
            run_bounded([str(tool),'-q','--no-progress','--separate-z-up-node',str(source),str(output)],work,seconds=settings.timeout_seconds,output=output)
            raw=output.read_bytes()
        except WorkerError as error:raise ConversionError(str(error)) from None
        output_scan=await scanner.scan(raw)
        if output_scan.status!='CLEAN':raise ConversionError('변환 GLB 악성코드 검사를 통과하지 못했습니다.')
        try:canonical,manifest=validate_model(raw)
        except AssetValidationError as error:raise ConversionError('변환 GLB: '+str(error)) from None
        canonical_scan=await scanner.scan(canonical)
        if canonical_scan.status!='CLEAN':raise ConversionError('정규화 GLB 악성코드 검사를 통과하지 못했습니다.')
        metadata={'kind':'OFFLINE_IFC_CONVERSION','at':utcnow(),'input_sha256':hashlib.sha256(data).hexdigest(),
                  'converter_version':version,'tool_manifest_sha256':settings.manifest_sha256,'output_sha256':hashlib.sha256(canonical).hexdigest(),
                  'scan':scan.model_dump(mode='json'),'output_scan':output_scan.model_dump(mode='json'),'canonical_scan':canonical_scan.model_dump(mode='json'),
                  'geometry':manifest.model_dump(mode='json'),'rights_review_required':True,'interior_verified':False,
                  'private_work_directory_acl_applied':True,
                  'network_isolation':'Operator attestation required; Job limits do not implement a firewall.'}
        return canonical,metadata
