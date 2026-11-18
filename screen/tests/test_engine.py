import copy
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from screen.contracts import Scenario
from screen import engine


def definition():
    return json.loads((Path(__file__).parents[1] / 'data/warehouse.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('change', ['too-soon', 'duplicate', 'reference', 'nan', 'budget'])
def test_invalid_scenarios_fail(change):
    value = definition()
    if change == 'too-soon':
        value['events'][1]['at_seconds'] = 119
    elif change == 'duplicate':
        value['entities'][1]['id'] = value['entities'][0]['id']
    elif change == 'reference':
        value['events'][0]['patch']['entities']['missing'] = {'fire': 2}
    elif change == 'nan':
        value['weather']['wind_speed'] = float('nan')
    else:
        value['buildings'] = [{**value['buildings'][0], 'id': f'B{i}', 'floors': 40, 'width': 120} for i in range(24)]
    with pytest.raises(ValidationError):
        Scenario.model_validate(value)


def test_minute_schedule_pause_and_no_delayed_burst():
    run = engine.new_run(definition(), 0)
    engine.command(run, 'start', 0)
    engine.tick(run, 59.999)
    assert not run['messages']
    engine.tick(run, 60)
    assert len(run['messages']) == 1 and run['scene']['entities'][0]['smoke'] == 3
    engine.command(run, 'pause', 70)
    engine.tick(run, 500)
    assert engine.elapsed(run, 500) == 70
    engine.command(run, 'resume', 500)
    engine.tick(run, 550)
    assert len(run['messages']) == 2
    engine.tick(run, 1500)
    assert len(run['messages']) == 3
    engine.tick(run, 1500.1)
    assert len(run['messages']) == 3
    assert engine.next_due(run) >= engine.elapsed(run, 1500) + 60


def test_confirmation_requires_due_time_and_public_has_no_hidden_people_or_prompts():
    value = definition()
    value['mode'] = 'confirm'
    run = engine.new_run(value, 0)
    engine.command(run, 'start', 0)
    with pytest.raises(HTTPException):
        engine.command(run, 'release', 59)
    engine.tick(run, 90)
    assert not run['messages']
    engine.command(run, 'release', 90)
    engine.command(run, 'note', 100, 'PRIVATE_SYNTHETIC_NOTE')
    public = engine.project(run, 100)
    assert 'scenario' not in public and 'notes' not in public and 'due_at' not in public
    text = json.dumps(public)
    assert 'PRIVATE_SYNTHETIC_NOTE' not in text and 'victim-a' not in text and 'private_prompt' not in text
    engine.command(run, 'release', 150)
    assert 'victim-a' in json.dumps(engine.project(run, 150))


def test_recovery_and_patches_are_deterministic():
    run = engine.new_run(definition(), 0)
    engine.command(run, 'start', 0)
    engine.tick(run, 65)
    engine.recover(run, 800)
    assert run['status'] == 'PAUSED' and run['elapsed'] == 65
    original = copy.deepcopy(run['scenario'])
    engine.command(run, 'resume', 900)
    for minute in range(1, 14):
        engine.tick(run, 900 + minute * 60)
    assert run['status'] == 'ENDED'
    assert run['scenario'] == original and run['seq'] > 12
