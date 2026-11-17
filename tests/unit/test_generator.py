import copy
import pytest
from pydantic import ValidationError
from apps.api.domain import Building, Exercise, Feature, validate_exercise
from apps.api.seeds import demo_exercise


def test_old_scene_roundtrip_supplies_defaults_without_claiming_interior_accuracy():
    original=demo_exercise().model_dump(mode='json')
    for building in original['subject']['buildings']:
        for field in ('basement_floors','roof_style','window_style','wall_finish','floor_outlines'):
            building.pop(field,None)
    restored=Exercise.model_validate(original)
    assert restored.subject.buildings[0].roof_style=='FLAT'
    assert restored.subject.buildings[0].floor_outlines==[]
    assert restored.subject.interior_verified is False


@pytest.mark.parametrize('points',[
    [[0,0],[8,8],[0,8],[8,0],[10,4]],
    [[0,0],[8,0],[8,8],[0,8],[0,0]],
    [[0,0],[8,0],[4,0],[4,8],[0,8]],
    [[0,0],[float('nan'),0],[8,8]],
])
def test_crossing_touching_degenerate_and_nonfinite_outlines_rejected(points):
    with pytest.raises(ValidationError):Building(id='B01',name='Synthetic',footprint=points)


def test_concave_and_basement_outline_are_preserved_and_duplicate_floor_rejected():
    data={'id':'B01','name':'Synthetic','floors':3,'basement_floors':2,
          'floor_outlines':[{'floor':-2,'footprint':[[0,0],[8,0],[8,4],[4,4],[4,8],[0,8]]}]}
    building=Building.model_validate(data)
    assert building.floor_outlines[0].floor==-2
    for bad in (0,-3,4):
        altered=copy.deepcopy(data);altered['floor_outlines'][0]['floor']=bad
        with pytest.raises(ValidationError):Building.model_validate(altered)
    data['floor_outlines']*=2
    with pytest.raises(ValidationError):Building.model_validate(data)


def test_interior_elements_are_anchors_with_bounded_dimensions_and_valid_floor_and_link():
    exercise=demo_exercise();building=exercise.subject.buildings[0];building.basement_floors=2
    feature=Feature(id='B01-B02-STAIR-01',name='가상 지하 계단',kind='STAIR',building_id='B01',floor=-2,width=2,depth=4)
    exercise.subject.features.append(feature)
    assert not [item for item in validate_exercise(exercise,readiness=False) if item['gate']=='G5']
    feature.floor=-3
    assert any('건물·층' in item['message'] for item in validate_exercise(exercise,readiness=False))
    feature.floor=1;feature.kind='PASSAGE';feature.linked_building_id='B99'
    assert any('연결통로' in item['message'] for item in validate_exercise(exercise,readiness=False))
    with pytest.raises(ValidationError):Feature(id='X',name='bad',kind='ROOM',width=0)
