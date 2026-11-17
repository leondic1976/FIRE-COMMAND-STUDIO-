import pytest
from pydantic import ValidationError
from apps.api.domain import Feature,Patch,validate_exercise
from apps.api.seeds import demo_exercise


@pytest.mark.parametrize('field,value',[('smoke',1000000000),('fire','4'),('radius','large'),('radius',float('inf')),('closed',1),('casualties',-1),('water',10000),('communication','x'*101)])
def test_initial_state_and_atomic_patch_reject_unbounded_or_wrong_types(field,value):
    with pytest.raises(ValidationError):Feature(id='synthetic-limit',name='합성 제한',kind='ZONE',state={field:value})
    with pytest.raises(ValidationError):Patch(feature_id='synthetic-limit',field=field,before=value,after=value)


def test_gate_revalidates_mutated_legacy_initial_states_before_publication():
    exercise=demo_exercise();exercise.subject.features[0].state['smoke']=10**9
    assert any(item['gate']=='G5' and '초기 상태' in item['message'] for item in validate_exercise(exercise,readiness=False))
