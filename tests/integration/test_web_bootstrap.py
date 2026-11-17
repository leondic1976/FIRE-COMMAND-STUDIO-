from pathlib import Path
import gzip
import re
import pytest


def test_built_web_assets_bootstrap_compression_and_security_headers(client):
    if not Path('dist/index.html').exists():
        pytest.skip('웹 빌드 후 정적 부트스트랩 시험 실행')
    response=client.get('/')
    assert response.status_code==200 and '<html lang="ko">' in response.text
    policy=response.headers['content-security-policy']
    assert "object-src 'none'" in policy and 'https://*.kakao.com' not in policy
    scripts=re.findall(r'src="(/assets/[^\"]+\.js)"',response.text)
    assert scripts
    with client.stream('GET',scripts[0],headers={'Accept-Encoding':'gzip'}) as asset:
        assert asset.status_code==200 and asset.headers.get('content-encoding')=='gzip'
        compressed=b''.join(asset.iter_raw())
    decoded=gzip.decompress(compressed)
    assert len(compressed)<len(decoded) and len(decoded)>10000
    icon=re.search(r'href="(/assets/[^\"]+\.svg)"',response.text)
    assert icon and client.get(icon.group(1)).headers['content-type'].startswith('image/svg+xml')
