"""Only pre-published AT_TIME events can be released by the server scheduler."""
import logging
from fastapi import HTTPException
from sqlalchemy import select
from . import engine
from .storage import records

logger=logging.getLogger(__name__)


def tick(store):
    with store.engine.connect() as conn:
        running=conn.execute(select(records).where((records.c.kind=='session') & (records.c.payload['status'].as_string()=='RUNNING'))).mappings().all()
    for row in running:
        state=row['payload']
        candidate=next((e for e in engine.candidates(state) if e['trigger']['kind']=='AT_TIME' and e['trigger']['auto_release'] and engine.trigger_matches(e,state) and engine.elapsed(state)>=state.get('deferred',{}).get(e['id'],0)),None)
        if candidate:
            eid=candidate['id']
            count=sum(e['kind']=='INJECT_RELEASED' and e['payload']['event_id']==eid for e in state['log'])
            try:
                store.mutate('session',row['id'],row['organization_id'],row['version'],'approved-scheduler','SCHEDULED_RELEASE',lambda current:engine.release(current,eid,'approved-scheduler'),key=f'auto:{eid}:{count}',request={'event_id':eid,'release_count':count})
            except HTTPException as exc:
                if exc.status_code!=409:logger.warning('사전 승인 사건 처리 실패: HTTP %s',exc.status_code)
