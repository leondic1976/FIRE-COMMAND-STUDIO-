from datetime import datetime, timedelta, timezone
import copy
import pytest
from pydantic import ValidationError
from apps.api.domain import Assignment, Building, Exercise, Patch, Subject, check_condition, condition_matches, validate_exercise
from apps.api.seeds import base_roles, demo_exercise


def errors(ex, readiness=False):
    return [i['message'] for i in validate_exercise(ex, readiness) if i['severity']=='ERROR']


def test_ac01_immutable_base_roles_and_correct_transition():
    original=base_roles()
    assert len(original)==7
    original[1].tasks[0]='기관 확장'
    assert base_roles()[1].tasks[0]!='기관 확장'
    mapping={r.id:r.department for r in base_roles()}
    assert mapping['situation_officer']=='대응계획부'
    assert mapping['resource_officer']=='자원지원부'
    assert mapping['safety_officer']=='현장지휘부'


@pytest.mark.parametrize('template',['factory','highrise','underground','compound'])
def test_seed_contracts(template):
    ex=demo_exercise(template=template)
    assert not errors(ex)
    assert len(ex.persons)==10 and len(ex.subject.buildings)>=3
    assert len(ex.events)>=6


def test_ac03_overlapping_and_historical_assignments():
    ex=demo_exercise()
    a=ex.assignments[0].model_copy(deep=True)
    a.id='future-overlap';a.role_id=ex.roles[1].id
    ex.assignments.append(a)
    assert any('겹침' in m for m in errors(ex))
    a.status='ENDED'
    assert not errors(ex)


def test_ac07_readiness_gates_cannot_be_bypassed():
    ex=demo_exercise()
    issues=validate_exercise(ex)
    assert sum(i['gate']=='G3' and i['severity']=='ERROR' for i in issues)==7
    ex.mode='DIAGNOSTIC'
    assert not errors(ex,True)
    assert any(i['gate']=='G3' and i['severity']=='WARNING' for i in validate_exercise(ex))


def test_ac02_reporting_cycles_and_missing_references():
    ex=demo_exercise();ex.roles[0].reports_to=ex.roles[1].id
    assert any('순환' in m for m in errors(ex))
    ex.roles[0].reports_to='unknown'
    assert any('보고 대상' in m for m in errors(ex))


@pytest.mark.parametrize('mutation,expected',[
    (lambda e:e.events[0].next_event_ids.append('unknown'),'후속 사건'),
    (lambda e:e.events[2].next_event_ids.append(e.events[0].id),'순환'),
    (lambda e:setattr(e.events[-1],'terminal',False),'종료'),
    (lambda e:e.events.append(e.events[0].model_copy(deep=True)),'중복 사건'),
    (lambda e:e.events[0].recipient_role_ids.append('unknown'),'수신 역할'),
    (lambda e:setattr(e.events[0].patches[0],'feature_id','unknown'),'없는 구역'),
    (lambda e:e.events[0].next_event_ids.clear(),'도달 불가능'),
])
def test_ac26_branch_errors(mutation,expected):
    ex=demo_exercise();mutation(ex)
    assert any(expected in m for m in errors(ex))


@pytest.mark.parametrize('mode',['REAL','VIRTUAL_ON_REAL_MAP'])
def test_ac09_11_mode_and_source_gates(mode):
    ex=demo_exercise();ex.subject.target_mode=mode
    assert errors(ex)
    ex.subject.map_context='REAL'
    if mode=='REAL':
        ex.subject.source.classification='PUBLIC';ex.subject.source.reviewer='가상 자동시험용 승인 참조'
    assert not errors(ex)


@pytest.mark.parametrize('rights',['unknown','restricted'])
def test_ac13_unknown_rights_blocked(rights):
    ex=demo_exercise();ex.subject.source.rights=rights
    assert any('권리' in m for m in errors(ex))


def test_ac16_registry_does_not_create_verified_interior():
    ex=demo_exercise();assert not ex.subject.interior_verified
    ex.subject.model_accuracy='VERIFIED'
    assert any('검증 근거' in m for m in errors(ex))


@pytest.mark.parametrize('data',[{'floors':-1},{'floors':0},{'floors':10000},{'width':-10},{'width':float('nan')},{'footprint':[[0,0],[1,1]]},{'footprint':[[0,0],[0,0],[0,0]]}])
def test_geometry_fuzz(data):
    with pytest.raises(ValidationError):Building(id='B01',name='test',**data)


@pytest.mark.parametrize('latitude,longitude',[(91,127),(37,181),(float('inf'),127),(float('nan'),127)])
def test_coordinate_bounds(latitude,longitude):
    raw=demo_exercise().subject.model_dump();raw.update(latitude=latitude,longitude=longitude)
    with pytest.raises(ValidationError):Subject.model_validate(raw)


def test_timezone_and_backup_validation():
    a=demo_exercise().assignments[0].model_dump()
    a['effective_from']=datetime.now()
    with pytest.raises(ValidationError):Assignment.model_validate(a)
    a=demo_exercise().assignments[0].model_dump();a['backups']=[a['person_id']]
    with pytest.raises(ValidationError):Assignment.model_validate(a)


def test_ac25_safe_dsl_and_injection_rejection():
    node={'op':'AND','conditions':[{'feature_id':'H01','field':'water','operator':'eq','value':'UNAVAILABLE'},{'feature_id':'B01','field':'smoke','operator':'gte','value':2}]}
    assert check_condition(node)
    assert condition_matches(node,{'H01':{'water':'UNAVAILABLE'},'B01':{'smoke':3}})
    assert not condition_matches(node,{'H01':{'water':'AVAILABLE'},'B01':{'smoke':3}})
    assert not check_condition({'expression':"__import__('os').system('bad')"})
    assert not check_condition({'feature_id':'H01','field':'water','operator':'eval','value':'bad'})
    assert not condition_matches({'feature_id':'H01','field':'smoke','operator':'gte','value':'x'},{'H01':{'smoke':2}})


def test_ac37_partial_roles_explicit():
    ex=demo_exercise();ex.assignments=ex.assignments[:1]
    assert any('1~3명' in m for m in errors(ex))
    ex.mode='SOLO';ex.simulated_roles=[r.id for r in ex.roles[1:]]
    assert not errors(ex)


def test_patch_fields_and_levels_are_bounded():
    for data in [{'field':'__proto__','after':1},{'field':'smoke','after':-1},{'field':'fire','after':999}]:
        with pytest.raises(ValidationError):Patch(feature_id='B01',before=0,**data)
