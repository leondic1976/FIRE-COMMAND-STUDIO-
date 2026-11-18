"""Pure, deterministic scenario transitions; the server supplies the clock."""
import copy
from uuid import uuid4
from fastapi import HTTPException

from .contracts import Scenario


def initial_scene(scenario):
    return {'site': copy.deepcopy(scenario['site']), 'buildings': copy.deepcopy(scenario['buildings']),
            'entities': copy.deepcopy(scenario['entities']), 'weather': copy.deepcopy(scenario['weather']),
            'damage': {}, 'water': True, 'power': True}


def log(run, kind, at, detail=''):
    run['seq'] += 1
    run['log'].append({'seq': run['seq'], 'kind': kind, 'elapsed': round(at, 3), 'detail': detail})


def new_run(scenario, now):
    scenario = Scenario.model_validate(scenario).model_dump(mode='json')
    return {'id': 'screen-' + uuid4().hex[:16], 'created_at': now, 'state_version': 1, 'seq': 0, 'scenario': scenario,
            'title': scenario['title'], 'status': 'READY', 'elapsed': 0., 'anchor': None,
            'checkpoint_elapsed': 0., 'checkpoint_at': now, 'last_release_elapsed': 0.,
            'scene': initial_scene(scenario), 'messages': [], 'next_event': 0, 'log': [], 'notes': []}


def elapsed(run, now):
    return run['elapsed'] + max(0., now - run['anchor']) if run['status'] == 'RUNNING' else run['elapsed']


def apply_patch(scene, patch):
    entities = {item['id']: item for item in scene['entities']}
    for id, changes in patch['entities'].items():
        entities[id].update({key: value for key, value in changes.items() if value is not None})
    if patch.get('weather') is not None:
        scene['weather'] = copy.deepcopy(patch['weather'])
    scene['damage'].update(patch.get('damage', {}))
    for key in ['water', 'power']:
        if patch.get(key) is not None:
            scene[key] = patch[key]


def next_due(run):
    index = run['next_event']
    events = run['scenario']['events']
    return max(events[index]['at_seconds'], run['last_release_elapsed'] + 60) if index < len(events) else None


def release(run, now):
    at = elapsed(run, now)
    due = next_due(run)
    if run['status'] != 'RUNNING' or due is None or at < due:
        raise HTTPException(409, '사건 공개 전 최소60초 간격과 실행 상태를 확인하세요.')
    event = run['scenario']['events'][run['next_event']]
    apply_patch(run['scene'], event['patch'])
    run['messages'].append({key: event[key] for key in ['id', 'title', 'message', 'source_label', 'certainty', 'priority', 'side']} | {'elapsed': round(at, 3)})
    run['next_event'] += 1
    run['last_release_elapsed'] = at
    run.update(checkpoint_at=now, checkpoint_elapsed=at)
    log(run, 'EVENT_RELEASED', at, event['id'])


def command(run, action, now, note=''):
    at = elapsed(run, now)
    if action in ('start', 'resume'):
        expected = 'READY' if action == 'start' else 'PAUSED'
        if run['status'] != expected:
            raise HTTPException(409, '현재 훈련 상태에서 실행할 수 없습니다.')
        run.update(status='RUNNING', anchor=now, checkpoint_at=now, checkpoint_elapsed=at)
    elif action == 'pause':
        if run['status'] != 'RUNNING':
            raise HTTPException(409, '진행 중인 훈련만 일시정지할 수 있습니다.')
        run.update(status='PAUSED', elapsed=at, anchor=None, checkpoint_elapsed=at)
    elif action == 'end':
        if run['status'] == 'ENDED':
            raise HTTPException(409, '이미 종료된 훈련입니다.')
        run.update(status='ENDED', elapsed=at, anchor=None, checkpoint_elapsed=at)
    elif action == 'release':
        if run['scenario']['mode'] != 'confirm':
            raise HTTPException(409, '확인 진행 모드에서만 수동 공개합니다.')
        release(run, now)
        return
    elif action == 'note':
        if not note.strip() or len(note) > 4000 or len(run['notes']) >= 500:
            raise HTTPException(422, '회의 기록은1~4000자, 최대500건입니다.')
        run['notes'].append({'text': note.strip(), 'elapsed': round(at, 3), 'event_id': run['messages'][-1]['id'] if run['messages'] else None})
    else:
        raise HTTPException(422, '알 수 없는 훈련 명령입니다.')
    log(run, action.upper(), at, 'private-note' if action == 'note' else '')
    run.update(checkpoint_at=now, checkpoint_elapsed=at)


def tick(run, now):
    if run['status'] != 'RUNNING':
        return
    at = elapsed(run, now)
    due = next_due(run)
    if due is not None and at >= due and run['scenario']['mode'] == 'auto':
        release(run, now)
    # No delayed burst: each release moves the earliest next release by60s.
    if next_due(run) is None and at >= max(run['scenario']['duration_seconds'], run['last_release_elapsed'] + 60):
        command(run, 'end', now)
    run.update(checkpoint_at=now, checkpoint_elapsed=at)


def recover(run, now):
    at = max(run['checkpoint_elapsed'], run['last_release_elapsed'], run['log'][-1]['elapsed'] if run['log'] else 0.)
    run.update(status='PAUSED', elapsed=at, anchor=None, checkpoint_at=now)
    log(run, 'RECOVERED', run['elapsed'], '서버 중단 후 일시정지 복구')


def project(run, now, operator=False):
    value = {key: copy.deepcopy(run[key]) for key in ['id', 'title', 'status', 'scene', 'messages', 'seq', 'state_version']}
    value.update(elapsed=elapsed(run, now), server_time=now, training_only=True, scientific_prediction=False)
    if not operator:
        value['scene']['entities'] = [item for item in value['scene']['entities'] if item['visible']]
        visible = {item['id'] for item in value['scene']['entities']}
        for item in value['scene']['entities']:
            if item.get('target_id') not in visible:
                item['target_id'] = None
    if operator:
        value.update(mode=run['scenario']['mode'], due_at=next_due(run), duration_seconds=run['scenario']['duration_seconds'],
                     event_count=len(run['scenario']['events']), released_count=run['next_event'], notes=copy.deepcopy(run['notes']), log=copy.deepcopy(run['log']))
    return value
