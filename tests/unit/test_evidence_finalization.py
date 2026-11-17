import hashlib
import json
import pytest
from scripts.finalize_evidence import finalize


def test_invalid_browser_report_does_not_overwrite_existing_evidence(tmp_path):
    api=tmp_path/'apps/api';api.mkdir(parents=True);code=api/'main.py';code.write_bytes(b'SYNTHETIC_CODE')
    digest=hashlib.sha256(code.name.encode()+code.read_bytes()).hexdigest()
    output=tmp_path/'docs/evidence';output.mkdir(parents=True)
    originals={name:'PREVIOUS_VERIFIED_SYNTHETIC_EVIDENCE' for name in ['soak-60min.json','pytest-final.json','browser-final.json','source-sha256.json']}
    for name,content in originals.items():(output/name).write_text(content)
    soak=tmp_path/'soak.json';soak.write_text(json.dumps({'complete':True,'passed':True,'errors':[],'elapsed_seconds':3601,'clients':12,'kind':'AUTOMATED_SYNTHETIC_SOAK','real_user_pilot':False,'api_source_sha256':digest}))
    junit=tmp_path/'pytest.xml';junit.write_text('<testsuites><testsuite tests="1" errors="0" failures="0" skipped="0" time="1.0"/></testsuites>')
    browser=tmp_path/'chromium.xml';browser.write_text('<testsuites><testsuite tests="6" errors="0" failures="1" skipped="0" time="1.0"/></testsuites>')
    with pytest.raises(ValueError,match='incomplete or failed'):finalize(tmp_path,soak,junit,[browser])
    assert all((output/name).read_text()==content for name,content in originals.items())
    assert not list(output.glob('*.tmp'))
