import hashlib
import json
import os
from pathlib import Path
import sys

import pytest
from apps.api.ifc_conversion import ConversionError,ConverterSettings,convert_ifc,validate_ifc
from apps.api.offline_process import WorkerError,run_bounded
from tests.asset_fixtures import FixtureScanner,ifc_building


async def test_default_ifc_conversion_has_no_process_or_scan_side_effect():
    scanner=FixtureScanner()
    with pytest.raises(ConversionError,match='설정 전'):await convert_ifc(ifc_building(),ConverterSettings(),scanner)
    assert not scanner.calls


@pytest.mark.parametrize('content',[b'PK\x03\x04',b'<!DOCTYPE IFC>',b'ISO-10303-21;',
    ifc_building().replace(b'SYNTHETIC_PROJECT',b'https://127.0.0.1/private'),
    ifc_building().replace(b'SYNTHETIC_PROJECT',b'file:///private'),
    ifc_building().replace(b'SYNTHETIC_PROJECT',b'../../private')])
def test_unsafe_or_unsupported_ifc_is_rejected(content):
    with pytest.raises(ConversionError):validate_ifc(content)


async def test_changed_converter_manifest_fails_before_processing(tmp_path):
    manifest=tmp_path/'bundle.json';manifest.write_text('{"files":{"IfcConvert.exe":"'+'0'*64+'"}}')
    settings=ConverterSettings(approved=True,approval_reference='Synthetic test, not institution approval',offline_host_confirmed=True,
                               manifest_path=str(manifest),manifest_sha256='1'*64)
    scanner=FixtureScanner()
    with pytest.raises(ConversionError,match='매니페스트 해시'):await convert_ifc(ifc_building(),settings,scanner)
    assert not scanner.calls


@pytest.mark.skipif(os.name!='nt',reason='Windows Job limits verified on Windows')
def test_offline_process_timeout_and_output_limit_are_enforced(tmp_path):
    with pytest.raises(WorkerError,match='제한시간'):
        run_bounded([sys.executable,'-I','-S','-c','import time;time.sleep(5)'],tmp_path,seconds=.3,memory_bytes=128*1024*1024)
    with pytest.raises(WorkerError,match='출력 제한'):
        run_bounded([sys.executable,'-I','-S','-c','print("x"*100000)'],tmp_path,seconds=5,memory_bytes=128*1024*1024)


@pytest.mark.skipif(os.getenv('RUN_IFC_TOOL_TESTS')!='1' or os.name!='nt',reason='Explicit local pinned converter probe')
async def test_actual_pinned_converter_with_synthetic_building(tmp_path):
    tool=Path('runtime/tools/ifcconvert-0.8.5/bundle.json').resolve()
    assert tool.is_file(),'Install the official pinned test bundle first'
    settings=ConverterSettings(approved=True,approval_reference='SYNTHETIC TOOL QA ONLY, NOT INSTITUTIONAL APPROVAL',offline_host_confirmed=True,
        manifest_path=str(tool),manifest_sha256=hashlib.sha256(tool.read_bytes()).hexdigest())
    scanner=FixtureScanner()
    content,metadata=await convert_ifc(ifc_building(),settings,scanner)
    assert content.startswith(b'glTF') and metadata['geometry']['bounds']==[[-16,0,-11],[16,12,11]]
    assert len(metadata['geometry']['nodes'])==3 and metadata['geometry']['triangles']==36
    assert '0.8.5' in metadata['converter_version'] and len(scanner.calls)==3
    assert not metadata['interior_verified'] and metadata['rights_review_required']
    artifact=Path('artifacts/ifc');artifact.mkdir(parents=True,exist_ok=True)
    (artifact/'converted-synthetic.glb').write_bytes(content)
    (artifact/'conversion-synthetic.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
