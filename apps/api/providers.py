"""Provider contracts are deliberately offline until institutional access is verified."""
from dataclasses import dataclass
from typing import Generic,Literal,Protocol,TypeVar
from .domain import Subject,Source,utcnow

Input=TypeVar('Input',contravariant=True)
Output=TypeVar('Output',covariant=True)
ProviderKind=Literal['building_registry','weather','hydrant','map','roadview','building_model','media']


@dataclass(frozen=True)
class Access:
    available:bool
    reason:str


@dataclass(frozen=True)
class ProviderResult(Generic[Output]):
    data:Output
    source:Source
    retrieved_at:str


class DataProvider(Protocol[Input,Output]):
    id:str
    kind:ProviderKind
    async def capabilities(self)->list[str]:...
    async def validate_access(self)->Access:...
    async def fetch(self,value:Input)->ProviderResult[Output]:...


class DisabledProvider:
    def __init__(self,id:str,kind:ProviderKind):self.id,self.kind=id,kind
    async def capabilities(self):return []
    async def validate_access(self):return Access(False,'기관 승인·인증·제공처 약관·실응답 검증 전 비활성')
    async def fetch(self,value):raise RuntimeError('비활성 공급자는 네트워크 요청을 수행하지 않습니다.')


class SyntheticSubjectProvider:
    id='local-synthetic'
    kind='building_model'
    async def capabilities(self):return ['manual_subject','procedural_3d','local_map','offline_training']
    async def validate_access(self):return Access(True,'합성자료만 사용')
    async def fetch(self,value:dict)->ProviderResult[Subject]:
        subject=Subject.model_validate(value)
        if subject.target_mode!='VIRTUAL' or subject.source.classification!='SYNTHETIC':
            raise ValueError('합성 공급자는 실제 자료를 생성하거나 검증하지 않습니다.')
        return ProviderResult(subject,subject.source,utcnow())


class DisabledAIAdapter:
    """Future interface, no credentials, no network, no implicit publication."""
    async def generate_scenario_draft(self,*args,**kwargs):raise RuntimeError('AI_PROVIDER=disabled')
    summarize_discussion=generate_scenario_draft
    suggest_feedback=generate_scenario_draft
    simulate_role_reply=generate_scenario_draft
    generate_virtual_texture=generate_scenario_draft
