"""Deterministic, append-only training commands and server-side audience projections."""
import copy
from datetime import datetime, timezone
from fastapi import HTTPException
from .domain import Exercise, active_assignments, condition_matches, utcnow, validate_exercise


def append(s, kind, actor, payload, visibility="STAFF", recipients=None):
    s["seq"] += 1
    entry = {"seq": s["seq"], "kind": kind, "actor_id": actor, "at": utcnow(), "simulated_seconds": elapsed(s), "payload": copy.deepcopy(payload), "visibility": visibility, "recipient_role_ids": recipients or []}
    s["log"].append(entry)
    return entry


def elapsed(s,at=None):
    value = s["elapsed_seconds"]
    if s["status"] == "RUNNING" and s.get("clock_started_at"):
        value += max(0, ((at or datetime.now(timezone.utc)) - datetime.fromisoformat(s["clock_started_at"])).total_seconds())
    return round(value, 2)


def new_session(id, ex: Exercise):
    return {"id": id, "exercise": ex.model_dump(mode="json"), "roster": [a.model_dump(mode="json") for a in ex.assignments], "status": "READY", "stage": "CONTROL_GROUP" if ex.organization_type == "CONTROL_GROUP" else "FIELD_COMMAND", "state_version": 1, "seq": 0,
        "scene": {f.id: dict(f.state) for f in ex.subject.features}, "messages": [], "actions": [], "decisions": [],
        "observations": [], "improvements": [], "handovers": [], "released_ids": [], "skipped_ids": [], "deferred": {},
        "elapsed_seconds": 0, "clock_started_at": None, "log": [], "aar_approval": None, "created_at": utcnow()}


def recover_running(s):
    """Resume crashes as paused at the last committed event, never grade offline time."""
    if s["status"] != "RUNNING":
        return
    s["elapsed_seconds"] = s["log"][-1]["simulated_seconds"] if s["log"] else s["elapsed_seconds"]
    s["clock_started_at"] = None
    s["status"] = "PAUSED"
    append(s, "SESSION_RECOVERED", "recovery", {"reason": "서버 재시작: 마지막 기록 시각으로 복원·일시정지. 기록 이후 중단 구간은 시간평가에서 보류합니다."}, "PUBLIC")


def user_roles(s, user):
    return [a["role_id"] for a in s.get("roster", s["exercise"]["assignments"]) if a["person_id"] == user.get("person_id") and a["status"] == "ACTIVE" and datetime.fromisoformat(a["effective_from"]) <= datetime.now(timezone.utc) < datetime.fromisoformat(a["effective_to"])]


def current_exercise(s):
    return Exercise.model_validate({**s["exercise"], "assignments": s.get("roster", s["exercise"]["assignments"])})


def candidates(s):
    ex = s["exercise"]
    eligible = {ex["start_event_id"]}
    for event in ex["events"]:
        if event["id"] in s["released_ids"] or event["id"] in s["skipped_ids"]:
            eligible.update(event["next_event_ids"])
    return [e for e in ex["events"] if e["id"] in eligible and e["id"] not in s["released_ids"] and e["id"] not in s["skipped_ids"]]


def trigger_matches(e, s):
    t = e["trigger"]
    if t["kind"] == "MANUAL":
        return True
    if t["kind"] == "AT_TIME":
        return elapsed(s) >= t["at_seconds"]
    if t["kind"] == "ON_ACTION":
        return any(a["action_type"] == t["action"] for a in s["actions"])
    return condition_matches(t["condition"], s["scene"])


def release(s, event_id, actor):
    if s["status"] != "RUNNING":
        raise HTTPException(409, "진행 중인 훈련에서만 사건을 공개합니다.")
    if event_id in s["released_ids"]:
        raise HTTPException(409, "이미 공개한 사건입니다. 재시도에는 같은 멱등키를 사용하세요.")
    ev = next((e for e in candidates(s) if e["id"] == event_id), None)
    if not ev or not trigger_matches(ev, s):
        raise HTTPException(409, "도달 가능한 사건이 아니거나 발생 조건이 충족되지 않았습니다.")
    if elapsed(s) < s.get("deferred", {}).get(event_id, 0):
        raise HTTPException(409, "연기된 사건의 공개 시각이 아직 아닙니다.")
    for p in ev["patches"]:
        current = s["scene"].get(p["feature_id"], {}).get(p["field"])
        if type(current) is not type(p["before"]) or current != p["before"]:
            raise HTTPException(409, f"장면 상태 충돌: {p['feature_id']}/{p['field']}. 공개 전 상태를 확인하세요.")
    for p in ev["patches"]:
        s["scene"][p["feature_id"]][p["field"]] = p["after"]
    ex = current_exercise(s)
    assignments = active_assignments(ex)
    recipients = {rid: [a.person_id for a in assignments if a.role_id == rid] for rid in ev["recipient_role_ids"]}
    message = {k: copy.deepcopy(ev[k]) for k in ("id", "title", "sender", "text", "recipient_role_ids", "visibility", "priority", "channel", "truth_status")}
    message.update({"at": utcnow(), "simulated_seconds": elapsed(s), "recipient_person_ids": recipients, "stages": [], "event_seq": s["seq"] + 1})
    message['media_cues']=copy.deepcopy(ev.get('media_cues',[]))
    s["messages"].append(message)
    s["released_ids"].append(event_id)
    append(s, "INJECT_RELEASED", actor, {"event_id": event_id, "title": ev["title"], "patches": ev["patches"], "message": message}, ev["visibility"], ev["recipient_role_ids"])


def control(s, command, actor):
    op = command["operation"]
    if op in ("start", "resume"):
        allowed = ("READY",) if op == "start" else ("PAUSED",)
        if s["status"] not in allowed:
            raise HTTPException(409, "현재 상태에서 시작/재개할 수 없습니다.")
        issues = [i for i in validate_exercise(current_exercise(s), readiness=op == "start") if i["severity"] == "ERROR"]
        if issues:
            raise HTTPException(422, {"reason": "시작/재개 시점의 편성·임무 품질 게이트 실패", "issues": issues})
        s["status"] = "RUNNING"
        s["clock_started_at"] = utcnow()
        append(s, "SESSION_STARTED" if op == "start" else "SESSION_RESUMED", actor, {}, "PUBLIC")
    elif op in ("pause", "end"):
        if s["status"] not in (("RUNNING",) if op == "pause" else ("RUNNING", "PAUSED")):
            raise HTTPException(409, "현재 상태에서 정지/종료할 수 없습니다.")
        s["elapsed_seconds"] = elapsed(s)
        s["clock_started_at"] = None
        s["status"] = "PAUSED" if op == "pause" else "ENDED"
        append(s, "SESSION_PAUSED" if op == "pause" else "SESSION_ENDED", actor, {"reason": command.get("reason", "")}, "PUBLIC")
    elif op == "release":
        release(s, command.get("event_id"), actor)
    elif op in ("defer", "skip"):
        if s["status"] not in ("RUNNING", "PAUSED") or not command.get("reason", "").strip():
            raise HTTPException(422, "사건 연기/건너뛰기에는 사유와 진행/정지 상태가 필요합니다.")
        ev = next((e for e in candidates(s) if e["id"] == command.get("event_id")), None)
        if not ev:
            raise HTTPException(409, "현재 후보 사건이 아닙니다.")
        if op == "skip":
            s["skipped_ids"].append(ev["id"])
        else:
            s["deferred"][ev["id"]] = elapsed(s) + command.get("delay_seconds", 60)
        append(s, "EVENT_" + op.upper(), actor, {"event_id": ev["id"], "reason": command["reason"]})
    elif op == "undo":
        if s["status"] != "PAUSED" or not command.get("reason", "").strip():
            raise HTTPException(409, "되돌림은 일시정지 후 사유를 남겨 실행합니다.")
        original = next((x for x in reversed(s["log"]) if x["kind"] == "INJECT_RELEASED" and x["payload"]["event_id"] in s["released_ids"]), None)
        if not original:
            raise HTTPException(409, "되돌릴 사건이 없습니다.")
        eid = original["payload"]["event_id"]
        if any(a.get("event_id") == eid for a in s["actions"]):
            raise HTTPException(409, "이미 조치가 연결된 사건은 삭제/재귀속 방지를 위해 되돌릴 수 없습니다. 사후 보정으로 남기세요.")
        reversed_patches = []
        for p in reversed(original["payload"]["patches"]):
            if s["scene"][p["feature_id"]][p["field"]] != p["after"]:
                raise HTTPException(409, "후속 변경과 충돌하는 되돌림입니다.")
            s["scene"][p["feature_id"]][p["field"]] = p["before"]
            reversed_patches.append({**p, "before": p["after"], "after": p["before"]})
        s["released_ids"].remove(eid)
        for m in s["messages"]:
            if m["id"] == eid:
                m["reverted"] = True
        append(s, "SCENE_REVERTED", actor, {"event_id": eid, "patches": reversed_patches, "reason": command["reason"]}, original["visibility"], original["recipient_role_ids"])
    elif op == "transition":
        if s["status"] not in ("RUNNING", "PAUSED") or not command.get("reason", "").strip() or not s["exercise"]["organization_approval"]:
            raise HTTPException(409, "통제단 전환은 기관 승인 편성 및 인계 확인·사유가 필요합니다.")
        if s["stage"] == "CONTROL_GROUP":
            raise HTTPException(409, "이미 통제단 단계입니다.")
        s["stage"] = "CONTROL_GROUP"
        mapping = {r["id"]: r["department"] for r in s["exercise"]["roles"]}
        append(s, "ORGANIZATION_TRANSITIONED", actor, {"departments": mapping, "handover": command["reason"], "approval": s["exercise"]["organization_approval"]}, "PUBLIC")
    else:
        raise HTTPException(422, "지원하지 않는 제어 명령입니다.")


def project(s, user):
    """Allow-list projection: never send future definitions, answer keys, or staff fields."""
    sampled_at=datetime.now(timezone.utc)
    staff = user["role"] in ("admin", "facilitator")
    evaluator = user["role"] == "evaluator"
    owner = s["exercise"].get("practice_owner_person_id")
    if owner and not (staff or evaluator) and (user["role"] != "participant" or owner != user.get("person_id")):
        raise HTTPException(403, "개인 연습은 본인과 허가된 진행·평가관만 열람합니다.")
    roles = user_roles(s, user)
    person = user.get("person_id")
    subject = copy.deepcopy(s["exercise"]["subject"])
    if not (staff or evaluator):
        subject['asset_bindings']=[binding for binding in subject.get('asset_bindings',[]) if binding['visibility']=='PUBLIC' and binding['source']['classification']!='INTERNAL']
    if user["role"] == "observer" and subject["source"]["classification"] != "SYNTHETIC":
        subject["buildings"] = []
        subject["features"] = []
        subject["external_layers"] = []
        subject['asset_bindings'] = []
        subject["latitude"] = subject["longitude"] = 0
        subject["source"] = {"provider": "제한된 참관 화면", "as_of": "비공개", "rights": "restricted", "confidence": "unverified", "classification": "INTERNAL"}
    visible = lambda x: staff or evaluator or x.get("visibility") == "PUBLIC" or (user["role"] == "participant" and bool(set(roles) & set(x.get("recipient_role_ids", []))))
    # Private injects can carry private spatial facts (e.g. water supply failure).
    # Reconstruct audience-visible scene facts instead of leaking the global state.
    audience_scene = {f["id"]: dict(f["state"]) for f in s["exercise"]["subject"]["features"]}
    if staff or evaluator:
        audience_scene = copy.deepcopy(s["scene"])
    else:
        for entry in s["log"]:
            if visible(entry):
                for patch in entry["payload"].get("patches", []):
                    audience_scene[patch["feature_id"]][patch["field"]] = patch["after"]
    if user["role"] == "observer" and subject["source"]["classification"] != "SYNTHETIC":
        audience_scene = {}
    messages = []
    for m in s["messages"]:
        historically_assigned = person and any(person in ids for ids in m["recipient_person_ids"].values())
        if visible(m) or historically_assigned:
            safe = copy.deepcopy(m)
            if not (staff or evaluator):
                safe.pop("recipient_person_ids", None)
                if safe["truth_status"] == "FALSE_REPORT":
                    safe["truth_status"] = "UNCONFIRMED"
                safe["stages"] = [stage for stage in safe["stages"] if stage.get("visibility") == "PUBLIC" or stage.get("person_id") == person]
            messages.append(safe)
    if not (staff or evaluator):
        eligible={binding['id'] for binding in subject.get('asset_bindings',[]) if binding['purpose']=='VIDEO'}
        shown=set()
        for message in messages:
            message['media_cues']=[cue for cue in message.get('media_cues',[]) if cue['binding_id'] in eligible and not message.get('reverted')]
            shown.update(cue['binding_id'] for cue in message['media_cues'])
        subject['asset_bindings']=[binding for binding in subject.get('asset_bindings',[]) if binding['purpose']!='VIDEO' or binding['id'] in shown]
    decisions = [copy.deepcopy(d) for d in s["decisions"] if d.get("visibility") == "PUBLIC" or staff or evaluator]
    safe_roles = [{"id": r["id"], "name": r["name"], "department": r["department"]} for r in s["exercise"]["roles"]]
    result = {"id": s["id"], "exercise_id": s["exercise"]["id"], "name": s["exercise"]["name"], "mode": s["exercise"]["mode"], "status": s["status"], "stage": s["stage"], "seq": s["seq"], "state_version": s["state_version"], "elapsed_seconds": elapsed(s,sampled_at), "clock_sampled_at": sampled_at.isoformat(), "subject": subject, "scene": audience_scene, "messages": messages, "decisions": decisions, "roles": safe_roles, "my_role_ids": roles, "watermark": "훈련용 · 가상 상황 · 시각효과는 공학적 예측이 아닙니다", "created_at": s["created_at"], "participant_count": len(s["exercise"]["persons"]), "assignment_count": len(active_assignments(current_exercise(s)))}
    result["timeline"] = [{"seq": e["seq"], "kind": e["kind"], "at": e["at"], "simulated_seconds": e["simulated_seconds"], "title": e["payload"].get("title", e["kind"])} for e in s["log"] if visible(e)]
    if staff:
        result.update({"candidates": [{**copy.deepcopy(e), "condition_met": trigger_matches(e, s), "deferred_until": s.get("deferred", {}).get(e["id"], 0)} for e in candidates(s)], "released_ids": s["released_ids"], "exercise": copy.deepcopy(s["exercise"]), "roster": copy.deepcopy(s.get("roster", [])), "handovers": s["handovers"]})
    if staff or evaluator:
        result.update({"observations": copy.deepcopy(s["observations"]), "improvements": copy.deepcopy(s["improvements"]), "actions": copy.deepcopy(s["actions"]), "log": copy.deepcopy(s["log"]), "aar_approval": s["aar_approval"]})
    elif user["role"] == "participant":
        result["actions"] = [copy.deepcopy(a) for a in s["actions"] if a["person_id"] == person]
        result["handovers"] = [copy.deepcopy(h) for h in s["handovers"] if person in (h["from_person_id"], h["to_person_id"])]
        if owner == person:
            practiced_role = s["exercise"]["assignments"][0]["role_id"]
            result["practice"] = {"difficulty": s["exercise"]["practice_difficulty"], "self_practice": True, "readiness": "사전 숙지 미확인 · 개인 연습 결과", "role": next(copy.deepcopy(r) for r in s["exercise"]["roles"] if r["id"] == practiced_role), "next_candidates": [{"id": e["id"], "condition_met": trigger_matches(e, s)} for e in candidates(s)]}
            result["practice_feedback"] = [e["payload"] for e in s["log"] if e["kind"] == "PRACTICE_FEEDBACK"]
    return result


def replay_state(s, seq):
    result = copy.deepcopy(s)
    result["scene"] = {f["id"]: dict(f["state"]) for f in s["exercise"]["subject"]["features"]}
    logs = [e for e in s["log"] if e["seq"] <= seq]
    result["log"] = logs
    for e in logs:
        for p in e["payload"].get("patches", []):
            result["scene"][p["feature_id"]][p["field"]] = p["after"]
    result["messages"] = [copy.deepcopy(m) for m in s["messages"] if m["event_seq"] <= seq]
    for message in result["messages"]:
        message["stages"] = [a for a in message["stages"] if a["seq"] <= seq]
        message["reverted"] = any(e["kind"] == "SCENE_REVERTED" and e["payload"]["event_id"] == message["id"] for e in logs if e["seq"] >= message["event_seq"])
    result["roster"] = copy.deepcopy(s["exercise"]["assignments"])
    for e in logs:
        if e["kind"] == "ROSTER_CHANGED":
            result["roster"] = copy.deepcopy(e["payload"]["roster"])
    result["actions"] = [a for a in s["actions"] if a["seq"] <= seq]
    result["observations"] = [e["payload"] for e in logs if e["kind"] == "OBSERVATION_RECORDED"]
    result["improvements"] = [e["payload"] for e in logs if e["kind"] == "IMPROVEMENT_ASSIGNED"]
    for e in logs:
        if e["kind"] == "IMPROVEMENT_COMPLETED":
            result["improvements"] = [copy.deepcopy(e["payload"]) if i["id"] == e["payload"]["id"] else i for i in result["improvements"]]
    result["handovers"] = [e["payload"] for e in logs if e["kind"] == "HANDOVER_UPDATED"]
    result["stage"] = "CONTROL_GROUP" if s["exercise"].get("organization_type") == "CONTROL_GROUP" or any(e["kind"] == "ORGANIZATION_TRANSITIONED" for e in logs) else "FIELD_COMMAND"
    result["aar_approval"] = None
    result["decisions"] = [d for d in s["decisions"] if d["seq"] <= seq]
    result["seq"] = seq
    result["elapsed_seconds"] = logs[-1]["simulated_seconds"] if logs else 0
    result["clock_started_at"] = None
    result["status"] = "REPLAY"
    return result
