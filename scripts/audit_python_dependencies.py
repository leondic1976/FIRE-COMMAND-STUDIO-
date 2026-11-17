"""Query public PyPI advisory metadata for this project's installed closure.

Only public package names/versions are sent. Does not upload files, configuration,
keys or model data. An empty result is scoped to that metadata at query time.
"""
import argparse
import asyncio
from datetime import datetime,timezone
from importlib.metadata import requires,version
import json
from pathlib import Path
import ssl

import httpx
from packaging.requirements import Requirement


def dependencies(root):
    pending=[Requirement(line) for line in (root/'requirements.txt').read_text(encoding='utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')]
    seen=set();names=set()
    while pending:
        requirement=pending.pop();name=requirement.name.lower().replace('_','-');extras=tuple(sorted(requirement.extras));key=(name,extras)
        if key in seen:continue
        seen.add(key);names.add(name)
        for declaration in requires(requirement.name) or []:
            child=Requirement(declaration)
            if child.marker is None or any(child.marker.evaluate({'extra':extra}) for extra in (extras or ('',))):pending.append(child)
    return sorted(names)


async def audit(root):
    semaphore=asyncio.Semaphore(6)
    # The OS trust store supports institution-installed trusted CAs. Never
    # disable TLS verification to obtain an advisory result.
    async with httpx.AsyncClient(verify=ssl.create_default_context(),timeout=20) as client:
        async def inspect(name):
            async with semaphore:
                installed=version(name)
                try:
                    response=await client.get(f'https://pypi.org/pypi/{name}/{installed}/json');response.raise_for_status()
                    findings=[{'id':item.get('id'),'aliases':item.get('aliases',[]),'fixed_in':item.get('fixed_in',[]),'link':item.get('link')}
                              for item in response.json().get('vulnerabilities',[]) if not item.get('withdrawn')]
                    return {'name':name,'version':installed,'queried':True,'findings':findings}
                except (httpx.HTTPError,ValueError):return {'name':name,'version':installed,'queried':False,'findings':[]}
        results=await asyncio.gather(*(inspect(name) for name in dependencies(root)))
    return {'generated_at':datetime.now(timezone.utc).isoformat(),'source':'PyPI release vulnerability metadata',
            'scope':'Installed project dependency closure including declared extras','tls_verification':True,
            'security_or_institutional_certification':False,'results':results,
            'passed':all(item['queried'] and not item['findings'] for item in results)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path('artifacts/python-advisories.json'))
    args=parser.parse_args();result=asyncio.run(audit(Path(__file__).resolve().parents[1]))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'packages':len(result['results']),'query_failures':sum(not item['queried'] for item in result['results']),
                      'packages_with_known_advisories':sum(bool(item['findings']) for item in result['results']),'passed':result['passed']}))
    raise SystemExit(0 if result['passed'] else 1)
