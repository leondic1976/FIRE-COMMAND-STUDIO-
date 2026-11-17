from __future__ import annotations

import asyncio
import copy
import csv
import hashlib
import io
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from pydantic import ValidationError
from sqlalchemy import select

from . import engine
from .auth import identity, issue_token, login_password, require, resolve_token, revoke
from .domain import Assignment,AssetBinding,AssetReview, Exercise, active_assignments, utcnow, validate_exercise
from .requests import (Action, Approval, Control, CreateExercise, Decision, DemoLogin, HandoverCommand, Improvement, ImprovementCompletion, Login, Observation, Practice, ReadinessAttempt, ReadinessReview, SaveExercise, Versioned)
from .safety import MAX_ASSET_BYTES, validate_glb, validate_xlsx
from .seeds import base_roles, demo_exercise, quiz_for
from .storage import Store, audit, records
from .scheduler import tick
from .middleware import BoundedBodyMiddleware
from .external_data import PublicDataRegistry
from .external_routes import install_external_routes
from .asset_routes import install_asset_routes
from .asset_scanner import LocalClamScanner
from .media_validation import MediaProcessor

ROOT = Path(__file__).resolve().parents[2]
DEMO_ORG = "org-synthetic"


def demo_profiles():
    profiles = [{"id": "facilitator", "label": "훈련 진행자", "role": "facilitator"}, {"id": "board", "label": "공동 대형상황판", "role": "board"}, {"id": "evaluator", "label": "평가관", "role": "evaluator"}, {"id": "observer", "label": "제한된 참관자", "role": "observer"}]
    return profiles + [{"id": f"person-{i:02}", "label": f"훈련요원 {i:02}", "role": "participant"} for i in range(1, 11)]


def create_app(db_url=None, demo_mode=None, external_settings=None, external_transport=None,asset_scanner=None,media_processor=None):
    demo = (os.environ.get("TRAINING_MODE", "demo") == "demo") if demo_mode is None else demo_mode
    secure_cookie = os.environ.get("COOKIE_SECURE", "false" if demo else "true").lower() == "true"
    if not demo and not secure_cookie:
        raise RuntimeError("운영 모드는 COOKIE_SECURE=true 및 승인된 HTTPS 환경이 필요합니다.")
    store = Store(db_url)
    if demo and not store.list("exercise", DEMO_ORG):
        store.create("exercise", "exercise-demo", DEMO_ORG, {**demo_exercise().model_dump(mode="json"), "state_version": 1})
    @asynccontextmanager
    async def lifespan(_app):
        with store.engine.connect() as conn:
            interrupted = conn.execute(select(records).where((records.c.kind == "session") & (records.c.payload["status"].as_string() == "RUNNING"))).mappings().all()
        for row in interrupted:
            try:
                store.mutate("session", row["id"], row["organization_id"], row["version"], "recovery", "SESSION_RECOVERED", engine.recover_running)
            except HTTPException as exc:
                if exc.status_code != 409:
                    raise
        stop = asyncio.Event()
        async def scheduler():
            while not stop.is_set():
                await asyncio.to_thread(tick, store)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=0.25)
                except asyncio.TimeoutError:
                    pass
        task = asyncio.create_task(scheduler())
        try:
            yield
        finally:
            stop.set()
            await task
    app = FastAPI(title="FIRE-COMMAND STUDIO", version="0.1.0", lifespan=lifespan, docs_url="/api/docs" if demo else None, openapi_url="/api/openapi.json" if demo else None)
    app.state.store = store
    app.state.demo = demo
    app.state.external_data = PublicDataRegistry(external_settings,transport=external_transport)
    install_external_routes(app)
    app.state.asset_scanner=asset_scanner or LocalClamScanner()
    app.state.media_processor=media_processor or MediaProcessor()
    install_asset_routes(app)
    app.add_middleware(BoundedBodyMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)
    allowed_origins = {origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "http://127.0.0.1:8010,http://localhost:8010,http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()}
    public_map_key = os.environ.get("VITE_KAKAO_JAVASCRIPT_KEY", "")
    maps_enabled = os.environ.get("VITE_KAKAO_MAPS_APPROVED") == "true" and len(public_map_key) == 32 and all(c in "0123456789abcdefABCDEF" for c in public_map_key)
    map_sources = " https://*.kakao.com https://*.daumcdn.net https://*.daum.net" if maps_enabled else ""
    websocket_origins = " ".join(sorted(origin.replace("https://", "wss://", 1).replace("http://", "ws://", 1) for origin in allowed_origins if origin.startswith(("http://", "https://"))))
    frame_sources = "https://*.kakao.com https://*.daum.net" if maps_enabled else "'none'"
    content_security_policy = f"default-src 'self'; script-src 'self'{map_sources}; style-src 'self' 'unsafe-inline'{map_sources}; img-src 'self' data: blob:{map_sources}; media-src 'self' blob:; connect-src 'self' {websocket_origins}{map_sources}; worker-src 'self' blob:{map_sources}; frame-src {frame_sources}; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    rate = {}

    @app.middleware("http")
    async def protect(request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin not in allowed_origins:
            return JSONResponse({"detail": "출처가 허용되지 않았습니다."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site" and request.url.path.startswith("/api"):
            return JSONResponse({"detail": "교차 사이트 API 접근 차단"}, status_code=403)
        content_length = request.headers.get("content-length", "0")
        if not content_length.isdigit() or int(content_length) > MAX_ASSET_BYTES + 100000:
            return JSONResponse({"detail": "요청 크기 제한 초과"}, status_code=413)
        response = await call_next(request)
        response.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin", "X-Frame-Options": "DENY", "Cache-Control": "no-store", "Permissions-Policy": "microphone=(), camera=(), geolocation=()", "Content-Security-Policy": content_security_policy})
        return response

    def login_limited(request):
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        history = [t for t in rate.get(key, []) if now-t < 60]
        if len(history) >= 30:
            raise HTTPException(429, "로그인 요청이 너무 많습니다. 잠시 후 다시 시도하세요.")
        rate[key] = history + [now]

    def set_login(response, user, previous_token=None):
        revoke(store, previous_token)
        token = issue_token(store, user)
        response.set_cookie("studio_session", token, httponly=True, secure=secure_cookie, samesite="strict", max_age=8*3600, path="/")
        return user

    def load_ex(id, user):
        data, version = store.load("exercise", id, user["organization_id"])
        data.pop("state_version", None)
        return Exercise.model_validate(data), version

    def mutation(kind, id, user, body, op, fn, key):
        if not key:
            raise HTTPException(428, "Idempotency-Key 헤더가 필요합니다.")
        return store.mutate(kind, id, user["organization_id"], body.expected_state_version, user["id"], op, fn, key=key, request=body.model_dump(mode="json", exclude={"expected_state_version"}))

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "training_only": True, "mode": "demo" if demo else "production", "ai_provider": "disabled", "external_dispatch": False, "schema_version": 2}

    @app.get('/api/v1/clock')
    def server_clock(user=Depends(identity)):
        require(user,'view')
        return {'server_time':utcnow(),'training_only':True}

    @app.get("/api/v1/auth/profiles")
    def profiles():
        return {"demo": demo, "profiles": demo_profiles() if demo else []}

    @app.post("/api/v1/auth/demo")
    def auth_demo(body: DemoLogin, request: Request, response: Response):
        login_limited(request)
        if not demo:
            raise HTTPException(404, "가상 데모 로그인이 비활성입니다.")
        profile = next((p for p in demo_profiles() if p["id"] == body.profile), None)
        if not profile:
            raise HTTPException(422, "허용된 가상 계정을 선택하세요.")
        return set_login(response, {"id": profile["id"], "name": profile["label"], "role": profile["role"], "organization_id": DEMO_ORG, "person_id": profile["id"] if profile["role"] == "participant" else None, "synthetic_only": True}, request.cookies.get("studio_session"))

    @app.post("/api/v1/auth/login")
    def login(body: Login, request: Request, response: Response):
        login_limited(request)
        return set_login(response, login_password(store, body.organization_id, body.username, body.password), request.cookies.get("studio_session"))

    @app.get("/api/v1/auth/me")
    def me(user=Depends(identity)):
        return user

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, response: Response):
        revoke(store, request.cookies.get("studio_session"))
        response.delete_cookie("studio_session", path="/")
        return {"logged_out": True}

    @app.get("/api/v1/roles/templates")
    def templates(user=Depends(identity)):
        require(user, "view")
        return {"readonly": True, "roles": [r.model_dump() for r in base_roles()], "institutional_review": "기관 SOP 검수 전 · 공개 법령 훈련용 요약"}

    @app.get("/api/v1/exercises")
    def exercises(user=Depends(identity)):
        require(user, "view")
        rows = store.list("exercise", user["organization_id"])
        if user["role"] not in ("admin", "facilitator"):
            return [{"id": r["id"], "name": r["name"], "published": r["published"], "state_version": r.get("state_version", 1)} for r in rows if r["published"] or any(a["person_id"] == user.get("person_id") for a in r["assignments"])]
        return [{"id": r["id"], "name": r["name"], "published": r["published"], "revision": r["revision"], "mode": r["mode"], "state_version": r.get("state_version", 1)} for r in rows]

    @app.post("/api/v1/exercises", status_code=201)
    def create_exercise(body: CreateExercise, user=Depends(identity)):
        require(user, "edit")
        id = "exercise-" + uuid4().hex[:12]
        ex = demo_exercise(id, body.template)
        if body.name:
            ex.name = body.name
        return store.create("exercise", id, user["organization_id"], {**ex.model_dump(mode="json"), "state_version": 1}, user["id"])

    @app.get("/api/v1/exercises/{id}")
    def exercise(id: str, user=Depends(identity)):
        require(user, "edit")
        ex, version = load_ex(id, user)
        return {"exercise": ex.model_dump(mode="json"), "state_version": version}

    @app.put("/api/v1/exercises/{id}")
    def save_exercise(id: str, body: SaveExercise, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "edit")
        if body.exercise.id != id:
            raise HTTPException(422, "훈련 ID가 다릅니다.")
        def change(data):
            if data["published"]:
                raise HTTPException(409, "발행본은 불변입니다. 복제 후 수정하세요.")
            prior = {r["id"]: r for r in data["roles"]}
            new = body.exercise.model_dump(mode="json")
            if new['external_reviews']!=data.get('external_reviews',[]) or new['subject']['external_layers']!=data['subject'].get('external_layers',[]):
                raise HTTPException(422,'외부 자료·검토 이력은 수집/검토 경로에서만 변경할 수 있습니다.')
            if new['asset_reviews']!=[AssetReview.model_validate(value).model_dump(mode='json') for value in data.get('asset_reviews',[])] or new['subject']['asset_bindings']!=[AssetBinding.model_validate(value).model_dump(mode='json') for value in data['subject'].get('asset_bindings',[])]:
                raise HTTPException(422,'자산 연결·권리 검토는 자산 검토 경로에서만 변경할 수 있습니다.')
            prior_features={feature['id']:feature for feature in data['subject']['features']}
            for feature in new['subject']['features']:
                old=prior_features.get(feature['id'],{})
                if (feature['data_origin'],feature['source_layer_id']) != (old.get('data_origin','SIMULATED'),old.get('source_layer_id')):
                    raise HTTPException(422,'자료 기반 객체의 출처 연결은 수집/검토 경로에서만 변경할 수 있습니다.')
            for role in new["roles"]:
                old = prior.get(role["id"])
                if old and {k:v for k,v in role.items() if k != "version"} != {k:v for k,v in old.items() if k != "version"}:
                    role["version"] = old["version"]+1
                elif old:
                    role["version"] = old["version"]
            new.update({"revision": data["revision"]+1, "published": False, "rehearsal_passed": False, "publication": None, "rehearsal_report": None, "readiness": data["readiness"], "reviews": data["reviews"]})
            data.clear()
            data.update(new)
        return mutation("exercise", id, user, body, "EXERCISE_SAVED", change, idempotency_key)

    @app.post("/api/v1/exercises/{id}/clone", status_code=201)
    def clone(id: str, user=Depends(identity)):
        require(user, "edit")
        ex, _ = load_ex(id, user)
        ex.id = "exercise-" + uuid4().hex[:12]
        ex.name += " · 새 편성"
        ex.published = False
        ex.rehearsal_passed = False
        ex.revision = 1
        ex.assignments = []
        ex.persons = []
        ex.readiness = {}
        ex.reviews = {}
        ex.organization_approval = ""
        ex.publication = None
        ex.rehearsal_report = None
        ex.subject.source.as_of = "새 자료 확인 필요"
        ex.subject.source.rights = "unknown"
        ex.subject.external_layers=[]
        ex.external_reviews=[]
        ex.subject.asset_bindings=[]
        ex.asset_reviews=[]
        for event in ex.events:event.media_cues=[]
        ex.subject.features=[feature for feature in ex.subject.features if feature.data_origin!='REFERENCE']
        ex.subject.source.reviewer=''
        ex.subject.source.confidence='unverified'
        ex.subject.interior_verified=False
        if ex.subject.model_accuracy=='VERIFIED':ex.subject.model_accuracy='APPROXIMATE'
        return store.create("exercise", ex.id, user["organization_id"], {**ex.model_dump(mode="json"), "state_version": 1}, user["id"])

    @app.post("/api/v1/exercises/{id}/validate")
    def validate(id: str, user=Depends(identity)):
        require(user, "edit")
        ex, _ = load_ex(id, user)
        issues = validate_exercise(ex)
        return {"valid": not any(i["severity"] == "ERROR" for i in issues), "issues": issues, "rehearsal_passed": ex.rehearsal_passed}

    @app.post("/api/v1/exercises/{id}/rehearse")
    def rehearse(id: str, body: Versioned, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "edit")
        def rehearsal(data):
            ex = Exercise.model_validate({k:v for k,v in data.items() if k != "state_version"})
            errors = [i for i in validate_exercise(ex, False) if i["severity"] == "ERROR"]
            if errors:
                raise HTTPException(422, errors)
            evs = {e.id:e for e in ex.events}
            paths = [0]
            def visit(eid, scene, trail):
                paths[0] += 1
                if paths[0] > 5000:
                    raise HTTPException(422, "분기 조합 5,000개 초과 — 시나리오를 분리하세요.")
                ev = evs[eid]
                changed = copy.deepcopy(scene)
                for p in ev.patches:
                    if changed[p.feature_id].get(p.field) != p.before:
                        raise HTTPException(422, f"리허설 상태 충돌: {eid}/{p.feature_id}/{p.field}")
                    changed[p.feature_id][p.field] = p.after
                for nxt in ev.next_event_ids:
                    visit(nxt, changed, trail+[eid])
            visit(ex.start_event_id, {f.id:dict(f.state) for f in ex.subject.features}, [])
            data["rehearsal_passed"] = True
            data["rehearsal_report"] = {"paths_visited": paths[0], "reviewer_id": user["id"], "at": utcnow(), "kind": "DETERMINISTIC_PATCH_CHECK"}
        return mutation("exercise", id, user, body, "REHEARSAL_PASSED", rehearsal, idempotency_key)

    @app.post("/api/v1/exercises/{id}/publish")
    def publish(id: str, body: Approval, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "edit")
        def change(data):
            ex = Exercise.model_validate({k:v for k,v in data.items() if k != "state_version"})
            errors = [i for i in validate_exercise(ex) if i["severity"] == "ERROR"]
            if errors or not ex.rehearsal_passed:
                raise HTTPException(422, {"issues": errors, "rehearsal_required": not ex.rehearsal_passed})
            if data["published"]:
                raise HTTPException(409, "이미 발행된 훈련입니다.")
            data["published"] = True
            data["publication"] = {"approver_id": user["id"], "at": utcnow(), "note": body.note, "scope": "SYNTHETIC_EXERCISE_VERSION"}
        return mutation("exercise", id, user, body, "EXERCISE_PUBLISHED", change, idempotency_key)

    @app.get("/api/v1/exercises/{id}/cards/{person_id}/{role_id}")
    def card(id: str, person_id: str, role_id: str, user=Depends(identity)):
        if user["role"] not in ("admin", "facilitator") and (user["role"] != "participant" or person_id != user.get("person_id")):
            raise HTTPException(403, "본인 임무카드만 열람할 수 있습니다.")
        ex, version = load_ex(id, user)
        role = next((r for r in ex.roles if r.id == role_id), None)
        assignment = next((a for a in ex.assignments if a.role_id == role_id and (a.person_id == person_id or person_id in a.backups)), None)
        if not role or not assignment:
            raise HTTPException(404, "배정 또는 대체 지정된 카드가 없습니다.")
        questions = [{k:v for k,v in q.items() if k not in ("answer", "reason")} for q in quiz_for(role)]
        return {"role": role.model_dump(), "person_id": person_id, "reports_to": next((r.name for r in ex.roles if r.id == role.reports_to), "승인된 기관 지휘체계"), "backups": assignment.backups, "quiz": questions, "readiness": ex.readiness.get(f"{person_id}:{role_id}"), "review": ex.reviews.get(f"{person_id}:{role_id}"), "state_version": version, "pass_score": ex.pass_score, "watermark": "훈련용 · 기관 SOP 검수 전"}

    @app.get("/api/v1/exercises/{id}/my-cards")
    def my_cards(id: str, user=Depends(identity)):
        if user["role"] != "participant":
            raise HTTPException(403, "참가자 개인 임무 목록입니다.")
        ex, _ = load_ex(id, user)
        role_ids = {a.role_id for a in ex.assignments if a.person_id == user.get("person_id") or user.get("person_id") in a.backups}
        return {"roles": [r.model_dump() for r in ex.roles if r.id in role_ids]}

    @app.post("/api/v1/exercises/{id}/readiness")
    def readiness(id: str, body: ReadinessAttempt, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "participate")
        if user["role"] == "participant" and body.person_id != user.get("person_id"):
            raise HTTPException(403, "다른 사람의 숙지 결과를 작성할 수 없습니다.")
        def change(data):
            if data["published"]:
                raise HTTPException(409, "발행본의 숙지 결과는 변경하지 않습니다. 실행 중 대체자는 별도 인계 절차를 사용하세요.")
            role = next((r for r in data["roles"] if r["id"] == body.role_id), None)
            assigned = any(a["role_id"] == body.role_id and (a["person_id"] == body.person_id or body.person_id in a["backups"]) for a in data["assignments"])
            if not role or not assigned or role["version"] != body.acknowledged_version:
                raise HTTPException(422, "현재 카드 버전과 배정을 확인하세요.")
            from .domain import Role
            quiz = quiz_for(Role.model_validate(role))
            score = round(sum(body.answers.get(q["id"]) == q["answer"] for q in quiz)*100/len(quiz))
            key = f"{body.person_id}:{body.role_id}"
            old = data["readiness"].get(key, {})
            attempt = {"at": utcnow(), "score": score, "answers": body.answers, "acknowledged_version": role["version"], "explanation": body.explanation, "feedback": [{"question_id": q["id"], "correct": body.answers.get(q["id"]) == q["answer"], "reason": q["reason"]} for q in quiz]}
            data["readiness"][key] = {**attempt, "attempts": old.get("attempts", []) + [attempt]}
            data["reviews"].pop(key, None)
        return mutation("exercise", id, user, body, "READINESS_ATTEMPTED", change, idempotency_key)

    @app.post("/api/v1/exercises/{id}/readiness/review")
    def review(id: str, body: ReadinessReview, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "control")
        def change(data):
            if data["published"]:
                raise HTTPException(409, "발행된 훈련은 변경할 수 없습니다.")
            key = f"{body.person_id}:{body.role_id}"
            if key not in data["readiness"]:
                raise HTTPException(409, "이해도 검사를 먼저 완료하세요.")
            data["reviews"][key] = {"approved": body.approved, "note": body.note, "reviewer_id": user["id"], "at": utcnow()}
        return mutation("exercise", id, user, body, "READINESS_REVIEWED", change, idempotency_key)

    @app.get("/api/v1/sessions")
    def sessions(user=Depends(identity)):
        require(user, "view")
        return [{"id": s["id"], "name": s["exercise"]["name"], "status": s["status"], "mode": s["exercise"]["mode"], "seq": s["seq"], "created_at": s["created_at"]} for s in store.list("session", user["organization_id"]) if not s["exercise"].get("practice_owner_person_id") or user["role"] in ("admin", "facilitator", "evaluator") or s["exercise"]["practice_owner_person_id"] == user.get("person_id")]

    @app.post("/api/v1/practice", status_code=201)
    def create_practice(body: Practice, user=Depends(identity)):
        if user["role"] != "participant" or not user.get("person_id"):
            raise HTTPException(403, "개인 연습은 참가자 계정으로 시작하세요.")
        from .domain import Person
        id = "practice-" + uuid4().hex[:12]
        ex = demo_exercise("exercise-"+uuid4().hex[:12], body.template)
        role = next((r for r in ex.roles if r.id == body.role_id), None)
        if not role:
            raise HTTPException(422, "개인 연습 역할을 선택하세요.")
        ex.name = f"개인 임무연습 · {role.name} · 합성 동료"
        ex.mode = "SOLO"
        ex.practice_owner_person_id = user["person_id"]
        ex.practice_difficulty = body.difficulty
        ex.persons = [Person(id=user["person_id"], display_name=user["name"])]
        a = ex.assignments[0].model_copy(deep=True)
        a.role_id = role.id
        a.person_id = user["person_id"]
        a.backups = []
        ex.assignments = [a]
        ex.simulated_roles = [r.id for r in ex.roles if r.id != role.id]
        for event in ex.events:
            event.recipient_role_ids = [role.id]
            event.sender = "모의 동료 · " + event.sender
            event.visibility = "PRIVATE"
            if body.difficulty == "BEGINNER":
                event.text += " [초급 도움말] 출처·미확인 정보·내 임무·보고 대상을 확인하세요."
            elif body.difficulty == "ADVANCED":
                event.text += " [고급] 상충 정보와 미완료 요청이 동시에 도착했습니다. 우선순위와 재확인 계획을 설명하세요."
        errors = [i for i in validate_exercise(ex, False) if i["severity"] == "ERROR"]
        if errors:
            raise HTTPException(422, errors)
        # Actually rehearse each patch; this is not an asserted human approval.
        rehearsal = engine.new_session("rehearsal", ex)
        engine.control(rehearsal, {"operation": "start"}, "practice-engine")
        for event in ex.events:
            engine.release(rehearsal, event.id, "practice-engine")
        ex.published = True
        ex.rehearsal_passed = True
        ex.publication = {"scope": "SELF_PRACTICE_ONLY", "at": utcnow(), "human_approval": False, "note": "모의 개인 연습. 공동 훈련 사전 숙지·기관 승인을 대체하지 않음"}
        ex.rehearsal_report = {"kind": "DETERMINISTIC_PATCH_CHECK", "events_checked": len(ex.events)}
        store.create("exercise", ex.id, user["organization_id"], {**ex.model_dump(mode="json"), "state_version": 1}, user["id"])
        store.create("session", id, user["organization_id"], engine.new_session(id, ex), user["id"])
        return {"id": id, "exercise_id": ex.id}

    @app.post("/api/v1/practice/{id}/control")
    def practice_control(id: str, body: Control, user=Depends(identity), idempotency_key: str | None = Header(None)):
        if user["role"] != "participant" or body.operation not in ("start", "resume", "pause", "release", "end"):
            raise HTTPException(403, "개인 연습에서 허용한 제어가 아닙니다.")
        def change(s):
            if s["exercise"].get("practice_owner_person_id") != user.get("person_id"):
                raise HTTPException(403, "본인 개인 연습만 진행할 수 있습니다.")
            engine.control(s, body.model_dump(), user["id"])
        return mutation("session", id, user, body, "PRACTICE_CONTROL", change, idempotency_key)

    @app.post("/api/v1/exercises/{id}/sessions", status_code=201)
    def create_session(id: str, user=Depends(identity)):
        require(user, "control")
        ex, _ = load_ex(id, user)
        if not ex.published:
            raise HTTPException(409, "품질 게이트를 통과한 후 발행하세요.")
        errors = [i for i in validate_exercise(ex) if i["severity"] == "ERROR"]
        if errors:
            raise HTTPException(422, errors)
        sid = "session-" + uuid4().hex[:12]
        return store.create("session", sid, user["organization_id"], engine.new_session(sid, ex), user["id"])

    @app.get("/api/v1/sessions/{id}")
    def session(id: str, user=Depends(identity)):
        require(user, "view")
        s, _ = store.load("session", id, user["organization_id"])
        return engine.project(s, user)

    @app.get("/api/v1/board/sessions/{id}")
    def projection(id: str, user=Depends(identity)):
        require(user, "view")
        s, _ = store.load("session", id, user["organization_id"])
        return engine.project(s, {**user, "role": "board", "person_id": None})

    @app.post("/api/v1/sessions/{id}/control")
    def session_control(id: str, body: Control, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "control")
        return mutation("session", id, user, body, "CONTROL_"+body.operation.upper(), lambda s: engine.control(s, body.model_dump(), user["id"]), idempotency_key)

    @app.post("/api/v1/sessions/{id}/actions")
    def action(id: str, body: Action, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "participate")
        def change(s):
            if s["status"] != "RUNNING":
                raise HTTPException(409, "진행 중에만 보고·조치를 기록할 수 있습니다.")
            if user["role"] == "participant" and body.person_id != user.get("person_id"):
                raise HTTPException(403, "다른 사람의 보고를 기록할 수 없습니다.")
            assignments = active_assignments(engine.current_exercise(s))
            if not any(a.person_id == body.person_id and a.role_id == body.role_id for a in assignments):
                raise HTTPException(403, "현재 담당하지 않는 역할입니다.")
            m = next((m for m in reversed(s["messages"]) if m["id"] == body.event_id and not m.get("reverted")), None)
            if not m or (m["visibility"] != "PUBLIC" and body.role_id not in m["recipient_role_ids"]):
                raise HTTPException(403, "미공개·미수신 메시지에는 보고할 수 없습니다.")
            order = ["RECEIVED", "ACKNOWLEDGED", "VERIFIED", "REPORTED", "DECIDED", "REPLIED", "CLOSED"]
            prior = [a for a in m["stages"] if a["person_id"] == body.person_id and a["role_id"] == body.role_id]
            expected_stage = order[len(prior)] if len(prior) < len(order) else None
            if body.stage != expected_stage:
                raise HTTPException(409, f"다음 단계는 {expected_stage or '이미 완료'}입니다.")
            a = {**body.model_dump(exclude={"expected_state_version"}), "at": utcnow(), "simulated_seconds": engine.elapsed(s), "seq": s["seq"]+1, "actor_id": user["id"]}
            if m["visibility"] == "PRIVATE":
                a["visibility"] = "PRIVATE"
            m["stages"].append(a)
            s["actions"].append(a)
            engine.append(s, "MESSAGE_"+body.stage, user["id"], a, a["visibility"], [body.role_id])
            if s["exercise"].get("practice_owner_person_id") == body.person_id and body.stage in ("REPORTED", "CLOSED"):
                feedback = {"event_id": body.event_id, "role_id": body.role_id, "person_id": body.person_id, "action_seq": a["seq"], "text": "모의 동료: 보고를 수신했습니다. 출처·불확실성·요청 담당자·재보고 시각이 포함되었는지 스스로 확인하세요. 이 피드백은 정답 판정이나 공동훈련 점수가 아닙니다.", "retraining": "동일 임무를 다른 가상 상황에서 다시 설명·보고하세요."}
                engine.append(s, "PRACTICE_FEEDBACK", "scripted-colleague", feedback, "PRIVATE", [body.role_id])
        return mutation("session", id, user, body, "ACTION_RECORDED", change, idempotency_key)

    @app.post("/api/v1/sessions/{id}/decisions")
    def decision(id: str, body: Decision, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "participate")
        def change(s):
            if s["status"] != "RUNNING":
                raise HTTPException(409, "진행 중에만 지휘결론을 기록할 수 있습니다.")
            if user["role"] == "participant" and "incident_commander" not in engine.user_roles(s, user):
                raise HTTPException(403, "지휘결론은 지휘관 또는 진행자가 기록합니다.")
            if body.role_id not in {r["id"] for r in s["exercise"]["roles"]}:
                raise HTTPException(422, "담당 역할이 없습니다.")
            if body.event_id and body.event_id not in s["released_ids"]:
                raise HTTPException(422, "미공개 사건입니다.")
            if body.event_id and user["role"] == "participant":
                message = next(m for m in reversed(s["messages"]) if m["id"] == body.event_id and not m.get("reverted"))
                if message["visibility"] == "PRIVATE" and not set(engine.user_roles(s, user)) & set(message["recipient_role_ids"]):
                    raise HTTPException(403, "미수신 비공개 메시지를 지휘결론 근거로 참조할 수 없습니다.")
            d = {**body.model_dump(exclude={"expected_state_version"}), "at": utcnow(), "actor_id": user["id"], "seq": s["seq"]+1, "simulated_seconds": engine.elapsed(s)}
            s["decisions"].append(d)
            engine.append(s, "DECISION_LOGGED", user["id"], d, body.visibility)
        return mutation("session", id, user, body, "DECISION_LOGGED", change, idempotency_key)

    @app.get("/api/v1/sessions/{id}/replay")
    def replay(id: str, seq: int = 0, user=Depends(identity)):
        require(user, "view")
        s, _ = store.load("session", id, user["organization_id"])
        if seq < 0 or seq > s["seq"]:
            raise HTTPException(422, "재생 시퀀스 범위를 벗어났습니다.")
        return engine.project(engine.replay_state(s, seq), user)

    @app.post("/api/v1/sessions/{id}/handovers")
    def handovers(id: str, body: HandoverCommand, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "participate")
        staff = user["role"] in ("admin", "facilitator")
        def change(s):
            if s["status"] not in ("RUNNING", "PAUSED"):
                raise HTTPException(409, "진행/일시정지 상태에서만 인계를 실행합니다.")
            ex = engine.current_exercise(s)
            now = utcnow()
            if body.operation == "propose":
                if not staff:
                    raise HTTPException(403, "대체 발동은 진행자가 승인합니다.")
                if len(body.note.strip()) < 3:
                    raise HTTPException(422, "대체 발동 사유를 기록하세요.")
                current = next((a for a in active_assignments(ex) if a.role_id == body.role_id), None)
                if not current:
                    raise HTTPException(422, "현재 배치된 역할이 아닙니다.")
                available = {p.id for p in ex.persons if p.available}
                active_people = {a.person_id for a in active_assignments(ex)}
                proposed = next((p for p in current.backups if p in available and p not in active_people), None)
                if not proposed or body.to_person_id != proposed:
                    raise HTTPException(409, "가용한 대체 우선순위와 중복배치를 확인하세요. 1순위: " + str(proposed))
                if any(h["role_id"] == body.role_id and h["status"] != "ACTIVE" for h in s["handovers"]):
                    raise HTTPException(409, "진행 중인 인계가 있습니다.")
                h = {"id": "handover-"+uuid4().hex[:12], "role_id": body.role_id, "from_person_id": current.person_id, "to_person_id": proposed, "assignment_id": current.id, "status": "PROPOSED", "history": [{"status": "PROPOSED", "at": now, "actor_id": user["id"], "note": body.note}]}
                s["handovers"].append(h)
            else:
                h = next((h for h in s["handovers"] if h["id"] == body.handover_id), None)
                if not h:
                    raise HTTPException(404, "인계 기록이 없습니다.")
                if body.operation in ("accept", "card") and not staff and h["to_person_id"] != user.get("person_id"):
                    raise HTTPException(403, "대체자 본인만 수락·숙지할 수 있습니다.")
                expected = {"accept": "PROPOSED", "card": "ACCEPTED", "review": "CARD_CHECKED", "handover": "READINESS_REVIEWED", "activate": "HANDOVER_COMPLETE"}
                if h["status"] != expected[body.operation]:
                    raise HTTPException(409, "이전 인계 단계를 완료하세요.")
                if body.operation in ("review", "handover", "activate") and not staff:
                    raise HTTPException(403, "구두확인·인계·활성화는 진행자가 확인합니다.")
                if body.operation == "card":
                    role = next(r for r in ex.roles if r.id == h["role_id"])
                    quiz = quiz_for(role)
                    score = round(sum(body.answers.get(q["id"]) == q["answer"] for q in quiz)*100/len(quiz))
                    if body.acknowledged_version != role.version or score < ex.pass_score or len(body.note.strip()) < 5:
                        raise HTTPException(422, "현재 카드 열람·이해도 통과·업무 설명이 필요합니다.")
                    h["readiness"] = {"score": score, "answers": body.answers, "acknowledged_version": role.version, "explanation": body.note, "at": now}
                if body.operation == "review" and len(body.note.strip()) < 3:
                    raise HTTPException(422, "대체자 구두 설명 확인 근거를 기록하세요.")
                if body.operation == "handover":
                    if not all(len(t.strip()) >= 2 for t in (body.summary, body.unconfirmed, body.pending_tasks, body.note)):
                        raise HTTPException(422, "현재 상황·미확인 정보·미완료 임무·인수 확인을 기록하세요. 없으면 '없음'으로 명시하세요.")
                    h.update({"summary": body.summary, "unconfirmed": body.unconfirmed, "pending_tasks": body.pending_tasks, "acceptance": body.note})
                if body.operation == "activate":
                    old = next(a for a in s["roster"] if a["id"] == h["assignment_id"])
                    if old["status"] != "ACTIVE" or any(a.person_id == h["to_person_id"] for a in active_assignments(ex)):
                        raise HTTPException(409, "기존 배치 변경 또는 대체자 중복배치 충돌")
                    old["status"] = "ENDED"
                    old["effective_to"] = now
                    new = {**old, "id": "assignment-"+uuid4().hex[:12], "person_id": h["to_person_id"], "effective_from": now, "effective_to": (datetime.now(timezone.utc)+timedelta(hours=8)).isoformat(), "status": "ACTIVE", "backups": [p for p in old["backups"] if p != h["to_person_id"]]}
                    s["roster"].append(new)
                    h["activated_at"] = now
                    engine.append(s, "ROSTER_CHANGED", user["id"], {"handover_id": h["id"], "roster": copy.deepcopy(s["roster"])})
                h["status"] = {"accept": "ACCEPTED", "card": "CARD_CHECKED", "review": "READINESS_REVIEWED", "handover": "HANDOVER_COMPLETE", "activate": "ACTIVE"}[body.operation]
                h["history"].append({"status": h["status"], "at": now, "actor_id": user["id"], "note": body.note})
            engine.append(s, "HANDOVER_UPDATED", user["id"], h)
        return mutation("session", id, user, body, "HANDOVER_"+body.operation.upper(), change, idempotency_key)

    @app.post("/api/v1/sessions/{id}/observations")
    def observe(id: str, body: Observation, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "evaluate")
        def change(s):
            if body.event_id not in s["released_ids"]:
                raise HTTPException(422, "미공개 정보를 평가 근거로 삼을 수 없습니다.")
            message = next(m for m in reversed(s["messages"]) if m["id"] == body.event_id and not m.get("reverted"))
            if body.person_id not in message["recipient_person_ids"].get(body.role_id, []) and message["visibility"] != "PUBLIC":
                raise HTTPException(422, "미수신·인계 전 정보를 감점 근거로 삼을 수 없습니다.")
            if body.person_id not in {p["id"] for p in s["exercise"]["persons"]} or body.role_id not in {r["id"] for r in s["exercise"]["roles"]}:
                raise HTTPException(422, "평가 대상 역할/사람이 없습니다.")
            if body.action_seq is not None and not any(a["seq"] == body.action_seq and a["person_id"] == body.person_id and a["role_id"] == body.role_id and a["event_id"] == body.event_id for a in s["actions"]):
                raise HTTPException(422, "행동 증거의 귀속이 일치하지 않습니다.")
            if body.score is not None and body.action_seq is None:
                raise HTTPException(422, "점수에는 본인의 관찰행동 증거가 필요합니다. 증거가 부족하면 미관찰로 기록하세요.")
            if body.corrects_id and not any(o["id"] == body.corrects_id for o in s["observations"]):
                raise HTTPException(422, "정정할 원래 관찰기록이 없습니다.")
            observation = {**body.model_dump(exclude={"expected_state_version"}), "id": "obs-"+uuid4().hex[:12], "at": utcnow(), "evaluator_id": user["id"]}
            s["observations"].append(observation)
            s["aar_approval"] = None
            engine.append(s, "OBSERVATION_RECORDED", user["id"], observation)
        return mutation("session", id, user, body, "OBSERVATION_RECORDED", change, idempotency_key)

    @app.post("/api/v1/sessions/{id}/improvements")
    def improve(id: str, body: Improvement, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "evaluate")
        def change(s):
            try:
                datetime.strptime(body.due_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(422, "올바른 목표일을 입력하세요.")
            if not any(o["id"] == body.observation_id for o in s["observations"]) or body.owner_role_id not in {r["id"] for r in s["exercise"]["roles"]}:
                raise HTTPException(422, "개선과제의 관찰 증거/담당자 참조가 없습니다.")
            item = {**body.model_dump(exclude={"expected_state_version"}), "id": "imp-"+uuid4().hex[:12], "at": utcnow(), "status": "COMPLETED" if body.evidence.strip() else "OPEN"}
            s["improvements"].append(item)
            s["aar_approval"] = None
            engine.append(s, "IMPROVEMENT_ASSIGNED", user["id"], item)
        return mutation("session", id, user, body, "IMPROVEMENT_ASSIGNED", change, idempotency_key)

    @app.post("/api/v1/sessions/{id}/aar/approve")
    def approve_aar(id: str, body: Approval, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "evaluate")
        def change(s):
            if s["status"] != "ENDED":
                raise HTTPException(409, "훈련 종료 후 평가를 승인합니다.")
            s["aar_approval"] = {"evaluator_id": user["id"], "at": utcnow(), "note": body.note}
            engine.append(s, "AAR_APPROVED", user["id"], s["aar_approval"])
        return mutation("session", id, user, body, "AAR_APPROVED", change, idempotency_key)

    @app.post("/api/v1/sessions/{id}/improvements/{improvement_id}/complete")
    def complete_improvement(id: str, improvement_id: str, body: ImprovementCompletion, user=Depends(identity), idempotency_key: str | None = Header(None)):
        require(user, "evaluate")
        def change(s):
            item = next((i for i in s["improvements"] if i["id"] == improvement_id), None)
            if not item:
                raise HTTPException(404, "개선과제를 찾을 수 없습니다.")
            if item["status"] != "OPEN":
                raise HTTPException(409, "이미 완료 증거가 기록된 과제입니다.")
            item.update({"status": "COMPLETED", "evidence": body.evidence, "completion_note": body.note, "completed_at": utcnow(), "completed_by": user["id"]})
            s["aar_approval"] = None
            engine.append(s, "IMPROVEMENT_COMPLETED", user["id"], item)
        return mutation("session", id, user, body, "IMPROVEMENT_COMPLETED", change, idempotency_key)

    @app.get("/api/v1/sessions/{id}/aar")
    def aar(id: str, format: str = "json", user=Depends(identity)):
        require(user, "export")
        s, _ = store.load("session", id, user["organization_id"])
        with store.engine.begin() as conn:
            store.log(conn, user["organization_id"], user["id"], "AAR_EXPORTED", id)
        report = {"training_only": True, "name": s["exercise"]["name"], "mode": s["exercise"]["mode"], "organization_name": s["exercise"]["organization_name"], "roles": s["exercise"]["roles"], "persons": s["exercise"]["persons"], "subject": s["exercise"]["subject"], "revision": s["exercise"]["revision"], "readiness": s["exercise"]["readiness"], "readiness_reviews": s["exercise"]["reviews"], "assignments": s["exercise"]["assignments"], "current_roster": s.get("roster", s["exercise"]["assignments"]), "handovers": s["handovers"], "timeline": s["log"], "observations": s["observations"], "improvements": s["improvements"], "approval": s["aar_approval"], "ai_provider": "disabled", "generated_at": utcnow()}
        report['asset_provenance']=[]
        for binding in report['subject'].get('asset_bindings',[]):
            asset,_=store.load('asset',binding['asset_id'],user['organization_id'])
            report['asset_provenance'].append({'binding_id':binding['id'],'asset_id':binding['asset_id'],'original_sha256':asset['original_sha256'],
                'creator':asset['provenance']['creator'],'license_scope':asset['provenance']['license_scope'],
                'location_note':asset['provenance']['location_note'],'conversion_claim':asset['provenance'].get('conversion_claim'),
                'scan':asset['scan'],'canonical_scan':asset['canonical_scan']})
        if format == "json":
            return report
        if format != "markdown":
            raise HTTPException(422, "json 또는 markdown을 선택하세요. PDF는 화면 인쇄를 이용합니다.")
        def clean(value):
            value=str(value).replace('\\','\\\\').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace("\r", " ").replace("\n", " ").replace("|", "／")
            for mark in ['[',']','*','_','`','!','#']:value=value.replace(mark,'\\'+mark)
            return value
        def kst(value):
            return datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")
        def description(payload):
            message = payload.get("message", {})
            return " / ".join(str(v) for v in (payload.get("title"), message.get("text"), payload.get("text"), payload.get("summary"), payload.get("reason")) if v)
        lines = [f"# {clean(report['name'])}", "", "**훈련용 가상 자료 · 기관 SOP 검수 전 · 인사평정용 아님**", "", f"기관: {clean(report['organization_name'])} / 모드: {report['mode']}", f"대상물: {report['subject']['target_mode']} / 사건: {report['subject']['scenario_factuality']}", f"시나리오 버전: {report['revision']} · AI 비활성", f"출처: {clean(report['subject']['source']['provider'])} / {clean(report['subject']['source']['as_of'])}", "", "## 발행 시점 편성·숙지", "", "| 역할 | 담당자 | 카드 버전 | 사전 점수 | 구두 확인 |", "|---|---|---|---|---|"]
        for a in report["assignments"]:
            key=f"{a['person_id']}:{a['role_id']}"
            r=report['readiness'].get(key,{})
            review=report['readiness_reviews'].get(key,{})
            lines.append(f"| {a['role_id']} | {a['person_id']} | {r.get('acknowledged_version','미열람')} | {r.get('score','미응시')} | {'확인' if review.get('approved') else '미확인'} |")
        lines += ["", "## 타임라인", "", "| 순서 | 가상시각(초) | 기록시각 KST | 수행자 / 입력자 | 종류 | 내용 |", "|---|---|---|---|---|---|"]
        lines += [f"| {e['seq']} | {e['simulated_seconds']} | {kst(e['at'])} | {clean(e['payload'].get('person_id', e['actor_id']))} / {clean(e['actor_id'])} | {e['kind']} | {clean(description(e['payload']))} |" for e in report["timeline"]]
        lines += ["", "## 관찰·평가", ""]
        for o in report["observations"]:
            lines += [f"- {o['person_id']} / {o['role_id']} / {o['event_id']}: {o['score'] if o['score'] is not None else '미관찰'} — {clean(o['evidence'])}", f"  - 강점: {clean(o['strength'])}; 개선: {clean(o['improvement'])}; 불확실: {clean(o['uncertainty'])}"]
        lines += ["", "## 개선과제·재훈련", ""]
        lines += [f"- {clean(i['title'])}: {i['owner_role_id']} / {i['due_date']} / {clean(i['retraining'])} / 완료증거: {clean(i['evidence']) or '미완료'}" for i in report["improvements"]]
        lines += ["", "## 대체·인계", ""]
        lines += [f"- {h['role_id']}: {h['from_person_id']} → {h['to_person_id']} / {h['status']} / 미완료: {clean(h.get('pending_tasks','기록 없음'))}" for h in report['handovers']]
        if report['subject'].get('external_layers'):
            lines += ['', '## 발행 당시 공공 기준자료', '', '현장 실측·현재 사용 가능 보증이 아닙니다. 관측값은 화재 예측값이 아닙니다.', '']
            for layer in report['subject']['external_layers']:
                source=layer['source']
                lines += [f"### {clean(source['provider'])}", f"기준: {clean(source['as_of'])} / 수집: {kst(layer['retrieved_at'])}", f"출처: {clean(source['url'])}", f"수집본: {layer['import_id']} / SHA256: {layer['raw_sha256']}"]
                for fact in layer['records']:
                    values='; '.join(f'{key}={clean(value)}' for key,value in fact['fields'].items())
                    lines.append(f"- {clean(fact['name'])} / {clean(fact['external_id'])}: {values}")
                lines += [f"- 유의: {clean(warning)}" for warning in layer['warnings']]
        if report['subject'].get('asset_bindings'):
            lines += ['', '## 발행 당시 모델·사진과 검토 범위', '', '검사·이용권 검토는 현장 실측·실내 구조 또는 공학적 예측 검증과 구분합니다.', '']
            for binding,origin in zip(report['subject']['asset_bindings'],report['asset_provenance']):
                lines += [f"### {clean(binding['label'])}",f"대상: {binding['building_id']} / {binding['purpose']} / {binding['visibility']}",
                          f"원천: {clean(binding['source']['provider'])} / 기준 {clean(binding['source']['as_of'])}",f"제작·촬영: {clean(origin['creator'])}",
                          f"이용범위: {clean(origin['license_scope'])}",f"대조 범위: {clean(origin['location_note'])}",
                          f"자산: {binding['asset_id']} / SHA256 {binding['sha256']}",f"검토: {kst(binding['reviewed_at'])} / {clean(binding['source']['reviewer'])}",
                          f"원본 저작권 표시: {clean(binding['manifest'].get('copyright_notice',''))}"]
                if origin['conversion_claim']:
                    claim=origin['conversion_claim'];lines += [f"오프라인 변환기록(제공자 선언): {clean(claim['converter_version'])} / 원IFC {claim['input_sha256']}"]
                if binding['kind']=='VIDEO':
                    info=binding['manifest'];lines += [f"녹화 영상: {info['width']}×{info['height']} / {info['duration_seconds']:.2f}초 / {info['frame_rate']}fps / {clean(info['video_codec'])}",f"정규화 도구: {clean(info['processing_tool'])}"]
                    for entry in report['timeline']:
                        for cue in entry['payload'].get('message',{}).get('media_cues',[]):
                            if cue['binding_id']==binding['id']:lines += [f"사건 연결: {clean(entry['payload']['event_id'])} / SEQ {entry['seq']} / 객체 {clean(cue['feature_id'])} / 클립 {cue['clip_start_seconds']}~{cue['clip_end_seconds']}초"]
        lines += ["", "평가관 승인: " + (clean(report["approval"]) if report["approval"] else "승인 대기"), "", "실제 사고피해 감소·지휘역량의 인과적 향상은 이 보고서로 검증되지 않았습니다."]
        return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="aar-{id}.md"'})

    @app.get("/api/v1/providers")
    def providers(user=Depends(identity)):
        require(user, "view")
        return [{"id":"local","implemented":True,"available":True,"reason":"로컬 합성자료 사용 가능"},
                *[app.state.external_data.status(kind) for kind in ('building_registry','weather','hydrant')],
                {'id':'building_model','implemented':True,'available':app.state.asset_scanner.status()['configured'],'live_verified':False,'reason':'로컬 GLB/사진 입력 구현. 검사·이용권·공개범위 검토 후 사용'},
                {'id':'media','implemented':True,'available':app.state.asset_scanner.status()['configured'] and app.state.media_processor.status()['configured'],'live_verified':False,'reason':'녹화 영상·사건 동기 재생 구현. 실제 검사기·고정 도구·격리 호스트·이용권 검증 후 사용'},
                *[{"id":kind,"available":False,"reason":"기관 승인·인증·네트워크 검증 전 비활성"} for kind in ('kakao_map','roadview','ai')]]

    @app.post("/api/v1/ai/drafts")
    def ai_disabled(user=Depends(identity)):
        require(user, "edit")
        raise HTTPException(409, "AI 어댑터 비활성. 외부 전송·자동 임무 승인 없이 수동/규칙 기반 훈련을 사용하세요.")

    @app.post("/api/v1/assets/validate")
    async def asset(file: UploadFile = File(...), user=Depends(identity)):
        require(user, "edit")
        data = await file.read(MAX_ASSET_BYTES+1)
        if len(data) > MAX_ASSET_BYTES:
            raise HTTPException(413, "15MB 크기 제한 초과")
        name = file.filename or ""
        if Path(name).name != name or "/" in name or "\\" in name or not name.lower().endswith(".glb"):
            raise HTTPException(422, "GLB 바이너리만 구조 검증할 수 있습니다. IFC는 승인된 오프라인 변환이 필요합니다.")
        result = validate_glb(data)
        return {**result, "sha256": hashlib.sha256(data).hexdigest(), "publication_allowed": False, "status": "QUARANTINED", "reason": "구조검증만 완료. 실제자료 이용권·좌표·객체검수·악성코드 검사 승인 전 등록/발행 차단"}

    @app.post("/api/v1/imports/roster")
    async def import_roster(file: UploadFile = File(...), user=Depends(identity)):
        require(user, "edit")
        data = await file.read(1_000_001)
        if len(data) > 1_000_000:
            raise HTTPException(413, "명부는 1MB 이하로 입력하세요.")
        name = (file.filename or "").lower()
        try:
            if name.endswith(".csv"):
                rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
            elif name.endswith(".xlsx"):
                validate_xlsx(data)
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=False)
                if wb.active is None or wb.active.max_row is None or wb.active.max_column is None or wb.active.max_row > 501 or wb.active.max_column > 30:
                    wb.close()
                    raise ValueError("명부는 헤더 포함 501행·30열 이내여야 합니다.")
                values = iter(wb.active.values)
                headers = next(values)
                rows = []
                for row in values:
                    if len(rows) >= 500:
                        raise ValueError("500행 초과")
                    if any(isinstance(c, str) and c.startswith("=") for c in row):
                        raise ValueError("수식 허용 안 됨")
                    rows.append(dict(zip(headers, row)))
                wb.close()
            else:
                raise ValueError("CSV/XLSX만 허용")
            if not rows or len(rows) > 500:
                raise ValueError("1~500행의 명부 데이터가 필요합니다.")
            required = {"person_id", "display_name", "role_id", "effective_from", "effective_to", "shift_id"}
            errors, people, assignments = [], {}, []
            from .domain import Person
            for index, row in enumerate(rows, 2):
                try:
                    if not required <= set(row):
                        raise ValueError("필수 열 누락")
                    person = Person(id=str(row["person_id"]), display_name=str(row["display_name"]))
                    a = Assignment(id=f"import-{index}", role_id=str(row["role_id"]), person_id=person.id, effective_from=row["effective_from"], effective_to=row["effective_to"], shift_id=str(row["shift_id"]), backups=[b.strip() for b in str(row.get("backups") or "").split(";") if b.strip()])
                    people[person.id] = person.model_dump()
                    assignments.append(a.model_dump(mode="json"))
                except (ValueError, ValidationError) as e:
                    errors.append({"row": index, "message": str(e)[:300]})
            return {"persons": list(people.values()), "assignments": assignments, "errors": errors, "saved": False}
        except (ValueError, UnicodeError, StopIteration, KeyError, TypeError, IndexError, AttributeError, SyntaxError, OSError, csv.Error):
            raise HTTPException(422, "명부 형식 오류: UTF-8 CSV/XLSX와 필수 열을 확인하세요.")

    @app.get("/api/v1/audit")
    def audits(user=Depends(identity)):
        require(user, "audit")
        with store.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(audit).where(audit.c.organization_id == user["organization_id"]).order_by(audit.c.id.desc()).limit(200)).mappings()]

    @app.websocket("/ws/v1/sessions/{id}")
    @app.websocket("/ws/v1/board/{id}")
    async def websocket(ws: WebSocket, id: str):
        origin = ws.headers.get("origin")
        if origin and origin not in allowed_origins:
            await ws.close(code=1008)
            return
        try:
            user = resolve_token(store, ws.cookies.get("studio_session"))
            require(user, "view")
            store.load("session", id, user["organization_id"])
        except HTTPException:
            await ws.close(code=1008)
            return
        await ws.accept()
        version = None
        try:
            while True:
                user = resolve_token(store, ws.cookies.get("studio_session"))
                if ws.url.path.startswith("/ws/v1/board/"):
                    user = {**user, "role": "board", "person_id": None}
                s, current = store.load("session", id, user["organization_id"])
                if current != version:
                    await ws.send_json({"type": "SNAPSHOT", "session_id": id, "event_seq": s["seq"], "state_version": current, "state": engine.project(s, user)})
                    version = current
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=0.25)
                except asyncio.TimeoutError:
                    pass
        except HTTPException:
            await ws.close(code=1008)
        except (WebSocketDisconnect, RuntimeError):
            pass

    if (ROOT / "dist" / "assets").exists():
        app.mount("/assets", StaticFiles(directory=ROOT / "dist" / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith(("api/", "ws/")):
            raise HTTPException(404, "경로를 찾을 수 없습니다.")
        index = ROOT / "dist" / "index.html"
        if not index.exists():
            return PlainTextResponse("웹 빌드가 필요합니다: npm install && npm run build", status_code=503)
        return FileResponse(index)

    return app


