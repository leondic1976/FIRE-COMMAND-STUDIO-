from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from tests.conftest import session_version


def test_ac28_twelve_concurrent_commands_have_one_commit(client,session_id):
    sid=session_id;version=session_version(client,sid)
    def send(_):
        return client.post(f'/api/v1/sessions/{sid}/control',json={'expected_state_version':version,'operation':'release','event_id':'EV-01'},headers={'Idempotency-Key':uuid4().hex}).status_code
    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses=list(pool.map(send,range(12)))
    assert statuses.count(200)==1,statuses
    assert statuses.count(409)==11,statuses
    state=client.get(f'/api/v1/sessions/{sid}').json()
    assert len(state['messages'])==1 and state['scene']['B01-F02-Z01']['smoke']==1
