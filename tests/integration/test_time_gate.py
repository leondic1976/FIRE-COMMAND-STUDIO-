from datetime import datetime,timedelta,timezone
from tests.conftest import control,prepare,session_version


def test_expired_assignment_blocks_start_even_after_publication(client,app):
    sid=prepare(client)
    def expire(s):
        a=s['roster'][0]
        a['effective_from']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        a['effective_to']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    app.state.store.mutate('session',sid,'org-synthetic',session_version(client,sid),'test','SIMULATE_SHIFT_END',expire)
    r=control(client,sid,'start')
    assert r.status_code==422 and 'G2' in r.text
    assert client.get('/api/v1/sessions/'+sid).json()['status']=='READY'
