from typing import Literal
from pydantic import Field
from .domain import Contract, Exercise
from .external_data import ExternalQuery


class Login(Contract):
    organization_id: str = Field(max_length=80)
    username: str = Field(max_length=80)
    password: str = Field(max_length=300)


class DemoLogin(Contract):
    profile: str = Field(max_length=80)


class Practice(Contract):
    role_id: str
    template: Literal["factory", "highrise", "underground", "compound"] = "factory"
    difficulty: Literal["BEGINNER", "STANDARD", "ADVANCED"] = "BEGINNER"


class Versioned(Contract):
    expected_state_version: int = Field(ge=1)


class ExternalPreview(Versioned):
    request: ExternalQuery


class ExternalApply(Versioned):
    selected_ids: list[str] = Field(min_length=1,max_length=100)
    building_id: str = Field(default='B01',pattern=r'^B[0-9]{2,4}$')
    fields: list[Literal['name','use','floors']] = Field(default_factory=lambda:['floors','use'],max_length=3)
    approved_for_training: bool
    note: str = Field(min_length=3,max_length=1000)


class SaveExercise(Versioned):
    exercise: Exercise


class CreateExercise(Contract):
    template: Literal["factory", "highrise", "underground", "compound"] = "factory"
    name: str = Field(default="", max_length=160)


class ReadinessAttempt(Versioned):
    person_id: str
    role_id: str
    acknowledged_version: int = Field(ge=1)
    answers: dict[str, int] = Field(default_factory=dict)
    explanation: str = Field(min_length=5, max_length=2000)


class ReadinessReview(Versioned):
    person_id: str
    role_id: str
    approved: bool
    note: str = Field(min_length=3, max_length=2000)


class Control(Versioned):
    operation: Literal["start", "resume", "pause", "end", "release", "defer", "skip", "undo", "transition"]
    event_id: str | None = None
    reason: str = Field(default="", max_length=2000)
    delay_seconds: int = Field(default=60, ge=1, le=3600)


class Action(Versioned):
    event_id: str
    role_id: str
    person_id: str
    stage: Literal["RECEIVED", "ACKNOWLEDGED", "VERIFIED", "REPORTED", "DECIDED", "REPLIED", "CLOSED"]
    action_type: str = Field(default="report", min_length=1, max_length=80)
    text: str = Field(min_length=2, max_length=3000)
    visibility: Literal["PUBLIC", "PRIVATE"] = "PRIVATE"
    truth_status: Literal["CONFIRMED", "UNCONFIRMED", "FALSE_REPORT"] = "UNCONFIRMED"


class Decision(Versioned):
    summary: str = Field(min_length=3, max_length=3000)
    role_id: str
    report_at_seconds: int = Field(ge=0, le=86400)
    event_id: str = ""
    visibility: Literal["PUBLIC", "PRIVATE"] = "PUBLIC"


class HandoverCommand(Versioned):
    operation: Literal["propose", "accept", "card", "review", "handover", "activate"]
    handover_id: str = ""
    role_id: str = ""
    to_person_id: str = ""
    note: str = Field(default="", max_length=3000)
    summary: str = Field(default="", max_length=3000)
    unconfirmed: str = Field(default="", max_length=3000)
    pending_tasks: str = Field(default="", max_length=3000)
    answers: dict[str, int] = Field(default_factory=dict)
    acknowledged_version: int | None = None


class Observation(Versioned):
    person_id: str
    role_id: str
    event_id: str
    action_seq: int | None = None
    criterion: Literal["mission", "awareness", "execution", "collaboration", "safety", "command"]
    score: int | None = Field(default=None, ge=0, le=3)
    evidence: str = Field(min_length=3, max_length=3000)
    strength: str = Field(default="", max_length=2000)
    improvement: str = Field(default="", max_length=2000)
    uncertainty: str = Field(default="", max_length=1000)
    corrects_id: str | None = None


class Improvement(Versioned):
    title: str = Field(min_length=3, max_length=300)
    owner_role_id: str
    due_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    observation_id: str
    retraining: str = Field(min_length=3, max_length=2000)
    evidence: str = Field(default="", max_length=3000)


class Approval(Versioned):
    note: str = Field(min_length=3, max_length=2000)


class ImprovementCompletion(Versioned):
    evidence: str = Field(min_length=3, max_length=3000)
    note: str = Field(min_length=3, max_length=2000)
