"""Copy only completed synthetic verification evidence into reviewable docs.

Refuses incomplete/failed soak data and a changed backend source hash.
"""
import argparse
import hashlib
import json
from pathlib import Path
from defusedxml import ElementTree


def finalize(root: Path, soak_path: Path, pytest_path: Path, browser_reports=(), targeted_reports=()):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    soak = json.loads(soak_path.read_text(encoding='utf-8'))
    require(soak['complete'] and soak['passed'] and not soak['errors'], 'Soak is incomplete or failed')
    require(soak['elapsed_seconds'] >= 3600 and soak['clients'] == 12, 'Required duration/client count not met')
    require(soak['kind'] == 'AUTOMATED_SYNTHETIC_SOAK' and not soak['real_user_pilot'], 'Synthetic evidence only')
    source = hashlib.sha256()
    for path in sorted((root / 'apps' / 'api').glob('*.py')):
        source.update(path.name.encode())
        source.update(path.read_bytes())
    require(source.hexdigest() == soak['api_source_sha256'], 'Backend changed after test started')
    suites = ElementTree.parse(pytest_path).getroot().findall('testsuite')
    totals = {key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
              for key in ['tests', 'errors', 'failures', 'skipped']}
    require(totals['tests'] and not totals['errors'] and not totals['failures'], 'Pytest did not pass')
    totals['passed'] = totals['tests'] - totals['errors'] - totals['failures'] - totals['skipped']
    totals['seconds'] = round(sum(float(suite.attrib.get('time', 0)) for suite in suites), 3)
    totals['browser_tests_executed'] = bool(browser_reports)
    totals['note'] = 'API/단위/통합/보안 회귀 결과. 브라우저 실행 결과는 별도 보고서에 기록한다.'
    output = root / 'docs' / 'evidence'
    output.mkdir(parents=True, exist_ok=True)
    pending = {}

    def write(name, data):
        pending[name] = json.dumps(data, ensure_ascii=False, indent=2) + '\n'

    write('soak-60min.json', soak)
    write('pytest-final.json', totals)
    if browser_reports:
        browsers=[]
        for path in browser_reports:
            suites=ElementTree.parse(path).getroot().findall('testsuite')
            result={key:sum(int(suite.attrib.get(key,0)) for suite in suites) for key in ['tests','errors','failures','skipped']}
            require(result['tests']>=6 and not result['errors'] and not result['failures'] and not result['skipped'], 'Browser suite incomplete or failed')
            engine=next((name for name in ['chromium','firefox'] if name in path.name),None)
            require(engine is not None,'Browser engine missing from report name')
            environment=json.loads((root/'artifacts'/'browser'/f'{engine}-environment.json').read_text(encoding='utf-8'))
            require(environment['engine']==engine and environment['headless'] and not environment['existing_browser_profile_used'],'Unexpected browser environment')
            result.update(environment)
            result['seconds']=round(sum(float(suite.attrib.get('time',0)) for suite in suites),3)
            result['cases']=[case.attrib['name'] for suite in suites for case in suite.findall('testcase')]
            browsers.append(result)
        require({value['engine'] for value in browsers}=={'chromium','firefox'},'Both browser engines required')
        write('browser-final.json',{'synthetic_only':True,'browser_results':browsers,'institutional_release_approved':False,'real_lan_pilot':False,'target_pc_fps_verified':False})
    if targeted_reports:
        results=[]
        for path in targeted_reports:
            suites=ElementTree.parse(path).getroot().findall('testsuite')
            result={key:sum(int(suite.attrib.get(key,0)) for suite in suites) for key in ['tests','errors','failures','skipped']}
            require(result['tests']>0 and not result['errors'] and not result['failures'] and not result['skipped'],'Targeted browser regression failed')
            result['engine']=next(name for name in ['chromium','firefox'] if name in path.name)
            result['seconds']=round(sum(float(suite.attrib.get('time',0)) for suite in suites),3)
            result['cases']=[case.attrib['name'] for suite in suites for case in suite.findall('testcase')]
            results.append(result)
        write('browser-layout-final.json',{'scope':'Targeted browser regressions listed in cases; source/version scope is recorded with the release evidence','results':results,'synthetic_only':True})
    hashes = {}
    for folder in ['apps', 'packages', 'scripts', 'tests']:
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and path.suffix in {'.py', '.ts', '.tsx', '.css', '.json'}:
                hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    write('source-sha256.json', hashes)
    # Validate every supplied report before replacing any existing evidence.
    # A failed browser input must not publish only the new soak/Pytest portion.
    for name, content in pending.items():
        temporary = output / (name + '.tmp')
        try:
            temporary.write_text(content, encoding='utf-8')
            temporary.replace(output / name)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Saved completed synthetic evidence: {totals['passed']} Pytest passed; {soak['elapsed_seconds']}s soak.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--soak', type=Path, default=Path('artifacts/perf/soak-60min-final-stable.json'))
    parser.add_argument('--pytest', type=Path, default=Path('artifacts/tests/pytest-final.xml'))
    parser.add_argument('--browser-report', type=Path, action='append', default=[])
    parser.add_argument('--targeted-browser-report', type=Path, action='append', default=[])
    args = parser.parse_args()
    finalize(Path(__file__).resolve().parents[1], args.soak, args.pytest, args.browser_report, args.targeted_browser_report)
