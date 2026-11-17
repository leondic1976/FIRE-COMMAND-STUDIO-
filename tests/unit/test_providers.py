import pytest
from apps.api.providers import DisabledAIAdapter,DisabledProvider,SyntheticSubjectProvider
from apps.api.seeds import demo_exercise


async def test_ac15_offline_provider_and_access_failures():
    local=SyntheticSubjectProvider()
    assert (await local.validate_access()).available
    result=await local.fetch(demo_exercise().subject.model_dump())
    assert result.data.target_mode=='VIRTUAL' and result.source.confidence=='simulated'
    for kind in ('building_registry','weather','hydrant','map','roadview','building_model','media'):
        provider=DisabledProvider(kind,kind)
        assert not (await provider.validate_access()).available
        with pytest.raises(RuntimeError):await provider.fetch({'url':'http://unapproved.invalid'})


async def test_ac33_ai_methods_fail_closed():
    adapter=DisabledAIAdapter()
    for method in ('generate_scenario_draft','summarize_discussion','suggest_feedback','simulate_role_reply','generate_virtual_texture'):
        with pytest.raises(RuntimeError):await getattr(adapter,method)({'private':'unapproved'})
