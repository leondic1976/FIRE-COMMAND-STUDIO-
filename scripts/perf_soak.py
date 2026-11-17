"""12-client synthetic LAN-style soak. This does not replace the real 10-person pilot."""
import argparse
import hashlib
import asyncio
import json
import os
import platform
import time
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import httpx
import websockets


async def soak(base:str,duration:int,output:Path):
    started=time.monotonic();started_at=datetime.now(timezone.utc).isoformat()
    clients=[];tasks=[];latest={};errors=[];latencies=[];snapshots={};done=asyncio.Event()
    def source_hash():
        h=hashlib.sha256()
        for path in sorted((Path(__file__).resolve().parents[1]/'apps'/'api').glob('*.py')):
            h.update(path.name.encode());h.update(path.read_bytes())
        return h.hexdigest()
    api_hash=source_hash()
    environment={'os':platform.platform(),'cpu_count':os.cpu_count(),'python':platform.python_version(),'transport':'loopback HTTP/WebSocket','renderer':'not_measured','database':'SQLite local development'}
    async def request(client,method,path,body=None):
        r=await client.request(method,base+'/api/v1'+path,json=body,headers={'Idempotency-Key':uuid4().hex} if method!='GET' else {})
        if not r.is_success:raise RuntimeError(f'{method} {path}: HTTP {r.status_code}')
        return r.json()
    try:
        for profile in ['facilitator','evaluator']+[f'person-{i:02}' for i in range(1,11)]:
            c=httpx.AsyncClient(timeout=15);clients.append((profile,c))
            await request(c,'POST','/auth/demo',{'profile':profile})
        fac=clients[0][1]
        ex=await request(fac,'POST','/exercises',{'template':'factory','name':'자동 12접속 장시간 부하시험 · 합성 응답'})
        eid=ex['id']
        async def ex_version():return (await request(fac,'GET','/exercises/'+eid))['state_version']
        for a in ex['assignments']:
            body={'expected_state_version':await ex_version(),'person_id':a['person_id'],'role_id':a['role_id'],'acknowledged_version':1,'answers':{'report':1,'mission':0,'handover':2},'explanation':'자동부하시험 합성 답안: 임무·출처·보고선 확인. 실제 참석자의 숙지가 아닙니다.'}
            await request(fac,'POST',f'/exercises/{eid}/readiness',body)
            await request(fac,'POST',f'/exercises/{eid}/readiness/review',{'expected_state_version':await ex_version(),'person_id':a['person_id'],'role_id':a['role_id'],'approved':True,'note':'자동시험용 합성 구두확인. 인간 실증 아님.'})
        await request(fac,'POST',f'/exercises/{eid}/rehearse',{'expected_state_version':await ex_version()})
        await request(fac,'POST',f'/exercises/{eid}/publish',{'expected_state_version':await ex_version(),'note':'장시간 자동부하시험 전용 가상 발행'})
        session=await request(fac,'POST',f'/exercises/{eid}/sessions');sid=session['id']
        async def receive(profile,client):
            cookie='; '.join(f'{k}={v}' for k,v in client.cookies.items())
            uri=base.replace('http://','ws://').replace('https://','wss://')+f'/ws/v1/sessions/{sid}'
            while not done.is_set():
                try:
                    async with websockets.connect(uri,origin=base,additional_headers={'Cookie':cookie},max_size=8*1024*1024) as ws:
                        async for message in ws:
                            payload=json.loads(message)
                            if payload.get('type')!='SNAPSHOT':continue
                            version=payload['state_version']
                            if version<latest.get(profile,0):errors.append({'type':'version_regressed','profile':profile})
                            latest[profile]=version;snapshots[profile]=snapshots.get(profile,0)+1
                            state=payload['state']
                            if profile.startswith('person-') and ('exercise' in state or 'observations' in state or 'candidates' in state):errors.append({'type':'private_field_leak','profile':profile})
                            if done.is_set():break
                except asyncio.CancelledError:raise
                except Exception as exc:
                    errors.append({'type':'connection_interrupted','profile':profile,'exception':type(exc).__name__})
                    await asyncio.sleep(1)
        tasks=[asyncio.create_task(receive(profile,c)) for profile,c in clients]
        async def command(operation,**fields):
            version=(await request(fac,'GET','/sessions/'+sid))['state_version']
            at=time.monotonic()
            result=await request(fac,'POST',f'/sessions/{sid}/control',{'expected_state_version':version,'operation':operation,**fields})
            deadline=at+2
            while time.monotonic()<deadline and not all(latest.get(p,0)>=result['state_version'] for p,_ in clients):await asyncio.sleep(.025)
            delta=time.monotonic()-at
            latencies.append(delta)
            if not all(latest.get(p,0)>=result['state_version'] for p,_ in clients):errors.append({'type':'sync_timeout','version':result['state_version']})
        await command('start')
        for i in range(1,11):await command('release',event_id=f'EV-{i:02}')
        active_start=time.monotonic();next_check=active_start
        def report(final=False):
            current=time.monotonic();values=sorted(latencies)
            data={'kind':'AUTOMATED_SYNTHETIC_SOAK','real_user_pilot':False,'api_source_sha256':api_hash,'environment':environment,'started_at':started_at,'requested_seconds':duration,'elapsed_seconds':round(current-active_start,2),'clients':12,'snapshots':snapshots,'latest_versions':latest,'commands':len(latencies),'max_sync_seconds':round(max(values),3) if values else None,'p95_sync_seconds':round(values[min(len(values)-1,int(len(values)*.95))],3) if values else None,'errors':errors,'session_id':sid,'complete':final,'passed':final and not errors and current-active_start>=duration}
            output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            return data
        while time.monotonic()-active_start<duration:
            if time.monotonic()>=next_check:
                await command('pause');await command('resume');next_check=time.monotonic()+30
                data=report();print(json.dumps({'elapsed_seconds':data['elapsed_seconds'],'clients':len(latest),'errors':len(errors)},ensure_ascii=False),flush=True)
            await asyncio.sleep(min(1,max(.01,duration-(time.monotonic()-active_start))))
        await command('end',reason='자동 합성 부하시험 종료 · 실제 기관 시범훈련과 구분')
        final_state=await request(fac,'GET','/sessions/'+sid)
        injects=[e['payload']['event_id'] for e in final_state['log'] if e['kind']=='INJECT_RELEASED']
        if injects!=[f'EV-{i:02}' for i in range(1,11)]:errors.append({'type':'inject_missing_or_duplicate'})
        if [e['seq'] for e in final_state['log']]!=list(range(1,len(final_state['log'])+1)):errors.append({'type':'non_contiguous_event_log'})
        expected={'B01-F02-Z01':{'smoke':1,'casualties':3},'B01-F03-Z01':{'smoke':3,'fire':2},'ROAD01':{'closed':True},'H01':{'water':'UNAVAILABLE'},'B02':{'warning':True},'ENT01':{'closed':True},'PERIMETER01':{'radius':30},'V01':{'communication':'FAILED'}}
        for fid,fields in expected.items():
            if any(final_state['scene'].get(fid,{}).get(k)!=v for k,v in fields.items()):errors.append({'type':'final_scene_mismatch','feature_id':fid})
        if source_hash()!=api_hash:errors.append({'type':'api_source_changed_during_test'})
        final=report(True);final['api_source_sha256']=api_hash;output.write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(final,ensure_ascii=False),flush=True)
        if not final['passed']:raise RuntimeError('부하시험에서 오류 또는 시간 미달이 발견되었습니다.')
    finally:
        done.set()
        for t in tasks:t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await asyncio.gather(*(c.aclose() for _,c in clients))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8010')
    parser.add_argument('--duration',type=int,default=3600)
    parser.add_argument('--output',type=Path,default=Path('artifacts/perf/soak.json'))
    args=parser.parse_args()
    if args.duration<1:parser.error('duration must be positive')
    asyncio.run(soak(args.base_url.rstrip('/'),args.duration,args.output))
