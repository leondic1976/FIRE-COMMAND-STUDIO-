from apps.api.domain import validate_exercise,utcnow
from apps.api.seeds import demo_exercise
from apps.api import engine


def test_distinct_hazard_templates_have_distinct_scene_data():
    highrise=demo_exercise(template='highrise')
    assert highrise.subject.buildings[0].floors==18
    flood=demo_exercise(template='underground')
    assert flood.events[0].patches[0].field=='water'
    assert flood.events[0].patches[0].feature_id=='UG01'
    compound=demo_exercise(template='compound')
    assert any(p.field=='rain' for p in compound.events[0].patches)
    for ex in [highrise,flood,compound]:
        assert not [i for i in validate_exercise(ex,False) if i['severity']=='ERROR']
        session=engine.new_session('test',ex)
        session['status']='RUNNING';session['clock_started_at']=utcnow()
        for event in ex.events:engine.release(session,event.id,'test')
        assert len(session['messages'])==10


def test_statutory_organization_and_interior_cannot_be_claimed_without_basis():
    ex=demo_exercise();ex.roles[1].department='자원지원부'
    assert any(i['gate']=='G1' for i in validate_exercise(ex,False))
    ex=demo_exercise();ex.subject.interior_verified=True
    assert any('실내 검증' in i['message'] for i in validate_exercise(ex,False))
    ex=demo_exercise();ex.organization_type='CONTROL_GROUP'
    assert any('승인 편성' in i['message'] for i in validate_exercise(ex,False))
