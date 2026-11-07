from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import audit, db, policy
from .adapters.reference_mock import ReferenceMockAdapter
from .security import digest, expiry, hash_password, identifier, iso, now, safe_compare, secret_token, verify_password

COOKIE_SECURE = os.environ.get("TERRAVIA_COOKIE_SECURE", "false").lower() == "true"
ALLOWED_FIELDS = {"name", "email", "qualification", "phone", "address", "date_of_birth"}
SENSITIVE_FIELDS = {"phone", "address", "date_of_birth"}
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
REFERENCE_ADAPTER = ReferenceMockAdapter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.initialize()
    yield


app = FastAPI(title="TerraVia Citizen Service", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


class RegisterBody(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]{1,64}@[^\s@.]+(?:\.[^\s@.]+)+", value):
            raise ValueError("Enter a valid email address")
        return value


class LoginBody(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]{1,64}@[^\s@.]+(?:\.[^\s@.]+)+", value):
            raise ValueError("Enter a valid email address")
        return value


class ClaimBody(BaseModel):
    attribute: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    value: str | int | float | bool | None
    source_type: Literal["CITIZEN", "AUTHORITY_REFERENCE", "ORGANIZATION", "FAMILY_MEMORY"] = "CITIZEN"
    source_reference: str | None = Field(default=None, max_length=300)
    assurance: Literal["UNVERIFIED", "LOW", "SUBSTANTIAL", "HIGH"] = "UNVERIFIED"


class CredentialBody(BaseModel):
    type: str = Field(min_length=2, max_length=80)
    issuer: str = Field(min_length=2, max_length=180)
    external_identifier: str | None = Field(default=None, max_length=200)
    issued_at: str | None = None
    expires_at: str | None = None
    source_reference: str | None = Field(default=None, max_length=300)


class EvidenceBody(BaseModel):
    claim_id: str | None = None
    credential_id: str | None = None
    source_type: str = Field(min_length=2, max_length=80)
    source_reference: str | None = Field(default=None, max_length=300)
    verification_method: str = Field(min_length=2, max_length=100)
    assurance_level: Literal["LOW", "SUBSTANTIAL", "HIGH"] = "LOW"
    artifact_hash: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")


class RequestBody(BaseModel):
    requester: str = Field(min_length=2, max_length=180)
    purpose: str = Field(min_length=8, max_length=500)
    legal_basis: Literal["CONSENT", "CONTRACT", "LEGAL_OBLIGATION"]
    requested_fields: list[str] = Field(min_length=1, max_length=20)
    service_id: str
    expires_at: str | None = None


class ConsentBody(BaseModel):
    fields: list[str] = Field(min_length=1, max_length=20)
    expires_at: str | None = None


class NetworkBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class RelationshipBody(BaseModel):
    related_label: str = Field(min_length=2, max_length=100)
    relationship_type: str = Field(min_length=2, max_length=80)
    evidence_level: Literal["OFFICIALLY_VERIFIED", "STRONGLY_VERIFIED", "FAMILY_SUPPORTED", "LIVING_MEMORY", "HISTORICAL_ORAL_TRADITION", "UNCONFIRMED_MEMORY", "UNRESOLVED_CONFLICTING"]
    state: Literal["VERIFIED", "MUTUALLY_CONFIRMED", "FAMILY_REPORTED", "HISTORICAL_UNCERTAIN", "UNCONFIRMED", "DISPUTED", "PROPOSED"] = "FAMILY_REPORTED"


class FamilyItemBody(BaseModel):
    item_type: Literal["EVENT", "ARCHIVE", "LIVING_MEMORY", "RESEARCH"]
    title: str = Field(min_length=2, max_length=180)
    content: str = Field(min_length=1, max_length=12000)
    evidence_level: Literal["OFFICIALLY_VERIFIED", "STRONGLY_VERIFIED", "FAMILY_SUPPORTED", "LIVING_MEMORY", "HISTORICAL_ORAL_TRADITION", "UNCONFIRMED_MEMORY", "UNRESOLVED_CONFLICTING"]
    certainty: Literal["KNOWN", "UNCERTAIN", "UNKNOWN"]
    visibility: Literal["PRIVATE", "FAMILY"] = "PRIVATE"


class LifeEventBody(BaseModel):
    event_type: str = Field(min_length=2, max_length=100)
    occurred_range: str | None = Field(default=None, max_length=120)
    evidence_references: list[str] = Field(default_factory=list, max_length=20)
    risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    affected_domains: list[str] = Field(default_factory=list, max_length=20)


class LegacyItemBody(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    content: str = Field(min_length=1, max_length=12000)
    classification: Literal["L1", "L2", "L3", "L4"] = "L2"
    release_mode: Literal["PRIVATE_UNTIL_TRIGGER", "TIME_LOCKED", "CUSTODIAN_CONTROLLED", "FAMILY_RELEASE"] = "PRIVATE_UNTIL_TRIGGER"
    custodians: list[str] = Field(default_factory=list, max_length=5)


def error(code: str, message: str, category: str, status: int, *, retryable: bool = False, fields: dict | None = None):
    raise HTTPException(status_code=status, detail={"code": code, "message": message, "category": category,
        "retryable": retryable, "field_errors": fields or {}, "policy_reference": None})


def audited_denial(conn, user: dict, request: Request, code: str, message: str, category: str, status: int,
                   *, object_type: str, object_id: str | None = None, purpose: str | None = None):
    correlation = getattr(request.state, "correlation_id", "")
    audit.record(conn, actor=user["account_id"], action="SENSITIVE_ACTION_DENIED", object_type=object_type,
                 object_id=object_id, purpose=purpose, result=code, correlation_id=correlation)
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message,
        "category": category, "retryable": False, "field_errors": {}, "policy_reference": None,
        "correlation_id": correlation}})


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    supplied = request.headers.get("X-Correlation-ID", "")
    correlation = supplied[:100] if re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", supplied or "") else str(uuid4())
    request.state.correlation_id = correlation
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if not isinstance(detail, dict) or "code" not in detail:
        detail = {"code": "REQUEST_FAILED", "message": str(detail), "category": "VALIDATION" if exc.status_code < 500 else "INTERNAL",
                  "retryable": exc.status_code >= 500, "field_errors": {}, "policy_reference": None}
    detail["correlation_id"] = getattr(request.state, "correlation_id", "")
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    fields = {".".join(str(part) for part in issue["loc"] if part not in {"body", "query", "path", "header"}): issue["msg"] for issue in exc.errors()}
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_FAILED", "message": "Review the highlighted fields and try again.",
        "category": "VALIDATION", "retryable": False, "field_errors": fields, "policy_reference": None,
        "correlation_id": getattr(request.state, "correlation_id", "")}})


def request_db():
    return db.connect()


def user_context(tv_session: str | None = Cookie(default=None)) -> dict:
    if not tv_session:
        error("AUTHENTICATION_REQUIRED", "Sign in to continue.", "AUTHENTICATION", 401)
    conn = request_db()
    try:
        row = conn.execute("""SELECT a.id account_id,a.person_id,a.email,p.status person_status,s.csrf_hash
            FROM sessions s JOIN accounts a ON a.id=s.account_id JOIN persons p ON p.id=a.person_id
            WHERE s.token_hash=? AND s.expires_at>?""", (digest(tv_session), iso())).fetchone()
        if not row or row["person_status"] != "ACTIVE":
            error("SESSION_INVALID", "Your session expired or was revoked. Sign in again.", "AUTHENTICATION", 401)
        return dict(row)
    finally:
        conn.close()


def csrf_guard(user: dict = Depends(user_context), token: str | None = Cookie(default=None, alias="tv_csrf"),
               header: str | None = Header(default=None, alias="X-CSRF-Token")) -> dict:
    if not token or not header or not safe_compare(token, header) or not safe_compare(digest(token), user["csrf_hash"]):
        error("CSRF_REJECTED", "The request could not be verified. Reload and try again.", "AUTHORIZATION", 403)
    return user


def set_session(response: Response, account_id: str):
    raw, csrf = secret_token(), secret_token()
    with db.transaction() as conn:
        conn.execute("INSERT INTO sessions(token_hash,account_id,csrf_hash,created_at,expires_at) VALUES(?,?,?,?,?)",
                     (digest(raw), account_id, digest(csrf), iso(), expiry()))
        audit.record(conn, actor=account_id, action="SESSION_CREATED", object_type="session", result="SUCCESS")
    response.set_cookie("tv_session", raw, httponly=True, secure=COOKIE_SECURE, samesite="strict", max_age=8 * 3600, path="/")
    response.set_cookie("tv_csrf", csrf, httponly=False, secure=COOKIE_SECURE, samesite="strict", max_age=8 * 3600, path="/")


def ensure_owner(conn, table: str, record_id: str, person_id: str, *, person_column: str = "person_id"):
    if table not in {"claims", "credentials", "evidence", "conflicts", "applications", "data_requests", "consents", "transfers", "life_events", "legacy_vaults", "legacy_items", "notifications"}:
        raise ValueError("invalid ownership table")
    row = conn.execute(f"SELECT * FROM {table} WHERE id=? AND {person_column}=?", (record_id, person_id)).fetchone()
    if not row:
        error("NOT_FOUND", "The requested record was not found.", "AUTHORIZATION", 404)
    return dict(row)


def open_conflict(conn, person_id: str, attribute: str):
    claims = conn.execute("SELECT id,value_json FROM claims WHERE person_id=? AND attribute=? AND status='ACTIVE' ORDER BY created_at", (person_id, attribute)).fetchall()
    values = {row["value_json"] for row in claims}
    if len(values) < 2:
        return None
    existing = conn.execute("SELECT * FROM conflicts WHERE person_id=? AND attribute=? AND state IN ('OPEN','UNDER_REVIEW','DISPUTED')", (person_id, attribute)).fetchone()
    ids = json.dumps([row["id"] for row in claims])
    if existing:
        conn.execute("UPDATE conflicts SET claim_ids_json=?,updated_at=? WHERE id=?", (ids, iso(), existing["id"]))
        return existing["id"]
    conflict_id = identifier()
    conn.execute("INSERT INTO conflicts(id,person_id,attribute,claim_ids_json,state,opened_at,updated_at) VALUES(?,?,?,?,'OPEN',?,?)", (conflict_id, person_id, attribute, ids, iso(), iso()))
    return conflict_id


@app.get("/")
def home():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/health")
def health():
    conn = request_db()
    try:
        conn.execute("SELECT 1")
        return {"status": "ok", "service": "terravia-citizen-service", "version": "1.0.0"}
    finally:
        conn.close()


@app.post("/v1/auth/register", status_code=201)
def register(body: RegisterBody, response: Response, request: Request):
    account_id, person_id = identifier(), identifier()
    try:
        with db.transaction() as conn:
            conn.execute("INSERT INTO persons(id,status,created_at) VALUES(?,'ACTIVE',?)", (person_id, iso()))
            conn.execute("INSERT INTO accounts(id,person_id,email,password_hash,created_at) VALUES(?,?,?,?,?)", (account_id, person_id, str(body.email).lower(), hash_password(body.password), iso()))
            audit.record(conn, actor=account_id, action="PERSON_CREATED", object_type="person", object_id=person_id,
                         correlation_id=request.state.correlation_id)
    except Exception as exc:
        if "UNIQUE" in str(exc):
            error("ACCOUNT_EXISTS", "An account with this email already exists.", "CONFLICT", 409)
        raise
    set_session(response, account_id)
    return {"person_id": person_id, "identity_type": "TERRAVIA_PERSON_ID", "external_identifier": None, "status": "ACTIVE"}


@app.post("/v1/auth/login")
def login(body: LoginBody, response: Response, request: Request):
    key = str(body.email).lower()
    recent = [when for when in LOGIN_ATTEMPTS.get(key, []) if time.time() - when < 600]
    if len(recent) >= 8:
        error("RATE_LIMITED", "Too many sign-in attempts. Wait ten minutes and retry.", "RATE_LIMITED", 429, retryable=True)
    conn = request_db()
    try:
        row = conn.execute("SELECT id,password_hash FROM accounts WHERE email=? COLLATE NOCASE", (key,)).fetchone()
    finally:
        conn.close()
    if not row or not verify_password(body.password, row["password_hash"]):
        recent.append(time.time())
        LOGIN_ATTEMPTS[key] = recent
        error("INVALID_CREDENTIALS", "Email or password is incorrect.", "AUTHENTICATION", 401)
    LOGIN_ATTEMPTS.pop(key, None)
    set_session(response, row["id"])
    return {"status": "authenticated"}


@app.post("/v1/auth/logout")
def logout(response: Response, user: dict = Depends(csrf_guard), tv_session: str | None = Cookie(default=None)):
    with db.transaction() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (digest(tv_session or ""),))
        audit.record(conn, actor=user["account_id"], action="SESSION_REVOKED", object_type="session", result="SUCCESS")
    response.delete_cookie("tv_session", path="/", secure=COOKIE_SECURE, httponly=True, samesite="strict")
    response.delete_cookie("tv_csrf", path="/", secure=COOKIE_SECURE, samesite="strict")
    return {"status": "signed_out"}


@app.get("/v1/me")
def me(user: dict = Depends(user_context)):
    return {"person_id": user["person_id"], "email": user["email"], "identity_type": "TERRAVIA_PERSON_ID", "status": user["person_status"]}


@app.get("/v1/persons/{person_id}")
def person(person_id: str, user: dict = Depends(user_context)):
    if person_id != user["person_id"]:
        error("ACCESS_DENIED", "You may only view your own identity record.", "AUTHORIZATION", 403)
    conn = request_db()
    try:
        claims = conn.execute("SELECT id,attribute,value_json,source_type,source_reference,assurance,verification_status,status,created_at FROM claims WHERE person_id=? ORDER BY created_at", (person_id,)).fetchall()
        credentials = conn.execute("SELECT id,type,issuer,external_identifier,issued_at,expires_at,verification_status,source_reference,created_at FROM credentials WHERE person_id=? ORDER BY created_at", (person_id,)).fetchall()
        return {"person_id": person_id, "status": user["person_status"], "claims": [{**dict(r), "value": json.loads(r["value_json"])} for r in claims], "credentials": [dict(r) for r in credentials]}
    finally:
        conn.close()


@app.post("/v1/claims", status_code=201)
def create_claim(body: ClaimBody, request: Request, user: dict = Depends(csrf_guard)):
    claim_id = identifier()
    encoded = json.dumps(body.value, ensure_ascii=False, sort_keys=True)
    with db.transaction() as conn:
        conn.execute("INSERT INTO claims(id,person_id,attribute,value_json,source_type,source_reference,assurance,verification_status,status,created_at,created_by) VALUES(?,?,?,?,?,?,?,'UNVERIFIED','ACTIVE',?,?)",
                     (claim_id, user["person_id"], body.attribute, encoded, body.source_type, body.source_reference, body.assurance, iso(), user["account_id"]))
        conflict_id = open_conflict(conn, user["person_id"], body.attribute)
        audit.record(conn, actor=user["account_id"], action="CLAIM_ADDED", object_type="claim", object_id=claim_id,
                     correlation_id=request.state.correlation_id, after={"attribute": body.attribute, "source": body.source_type})
        if conflict_id:
            audit.record(conn, actor=user["account_id"], action="IDENTITY_CONFLICT_OPENED", object_type="identity_conflict", object_id=conflict_id,
                         correlation_id=request.state.correlation_id, result="REVIEW_REQUIRED")
    return {"id": claim_id, "status": "UNVERIFIED", "conflict_id": conflict_id, "authoritative": False}


@app.post("/v1/credentials", status_code=201)
def add_credential(body: CredentialBody, request: Request, user: dict = Depends(csrf_guard)):
    credential_id = identifier()
    with db.transaction() as conn:
        conn.execute("INSERT INTO credentials(id,person_id,type,issuer,external_identifier,issued_at,expires_at,verification_status,source_reference,created_at,created_by) VALUES(?,?,?,?,?,?,?,'UNVERIFIED',?,?,?)",
                     (credential_id, user["person_id"], body.type.strip(), body.issuer.strip(), body.external_identifier, body.issued_at, body.expires_at, body.source_reference, iso(), user["account_id"]))
        audit.record(conn, actor=user["account_id"], action="CREDENTIAL_LINKED", object_type="credential", object_id=credential_id,
                     correlation_id=request.state.correlation_id, after={"type": body.type, "issuer": body.issuer, "verification": "UNVERIFIED"})
    return {"id": credential_id, "verification_status": "UNVERIFIED", "source_of_truth": body.issuer}


@app.post("/v1/evidence", status_code=201)
def add_evidence(body: EvidenceBody, request: Request, user: dict = Depends(csrf_guard)):
    if not body.claim_id and not body.credential_id:
        error("EVIDENCE_TARGET_REQUIRED", "Link evidence to a claim or credential.", "VALIDATION", 422)
    evidence_id = identifier()
    with db.transaction() as conn:
        for table, item_id in (("claims", body.claim_id), ("credentials", body.credential_id)):
            if item_id:
                conn.execute(f"SELECT id FROM {table} WHERE id=? AND person_id=?", (item_id, user["person_id"])).fetchone() or error("NOT_FOUND", "The evidence target was not found.", "AUTHORIZATION", 404)
        conn.execute("INSERT INTO evidence(id,person_id,claim_id,credential_id,source_type,source_reference,captured_at,verification_method,assurance_level,evidence_status,artifact_hash,created_by) VALUES(?,?,?,?,?,?,?,?,?,'UNREVIEWED',?,?)",
                     (evidence_id, user["person_id"], body.claim_id, body.credential_id, body.source_type, body.source_reference, iso(), body.verification_method, body.assurance_level, body.artifact_hash, user["account_id"]))
        audit.record(conn, actor=user["account_id"], action="EVIDENCE_ATTACHED", object_type="evidence", object_id=evidence_id,
                     correlation_id=request.state.correlation_id, result="UNREVIEWED")
    return {"id": evidence_id, "status": "UNREVIEWED", "verification_status": "UNCHANGED"}


@app.get("/v1/conflicts")
def conflicts(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        rows = conn.execute("SELECT * FROM conflicts WHERE person_id=? ORDER BY opened_at DESC", (user["person_id"],)).fetchall()
        return [{**dict(r), "claim_ids": json.loads(r["claim_ids_json"])} for r in rows]
    finally:
        conn.close()


@app.post("/v1/conflicts/{conflict_id}/review")
def review_conflict(conflict_id: str, request: Request, user: dict = Depends(csrf_guard)):
    with db.transaction() as conn:
        conflict = ensure_owner(conn, "conflicts", conflict_id, user["person_id"])
        if conflict["state"] not in {"OPEN", "DISPUTED"}:
            error("CONFLICT_STATE_INVALID", "Only an open or disputed conflict can enter review.", "CONFLICT", 409)
        conn.execute("UPDATE conflicts SET state='UNDER_REVIEW',updated_at=? WHERE id=?", (iso(), conflict_id))
        audit.record(conn, actor=user["account_id"], action="CONFLICT_REVIEW_REQUESTED", object_type="identity_conflict", object_id=conflict_id,
                     correlation_id=request.state.correlation_id, result="HUMAN_REVIEW")
    return {"id": conflict_id, "state": "UNDER_REVIEW", "resolution": "A reviewer must resolve this conflict; claims were not merged or overwritten."}


@app.get("/v1/services")
def services(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        rows = conn.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
        return [{**dict(r), "required_fields": json.loads(r["required_fields_json"])} for r in rows]
    finally:
        conn.close()


@app.get("/v1/adapters")
def adapters(user: dict = Depends(user_context)):
    descriptor = REFERENCE_ADAPTER.descriptor
    return [{"id": descriptor.adapter_id, "name": descriptor.name, "mode": descriptor.mode,
        "version": descriptor.version, "capabilities": descriptor.capabilities,
        "allowed_fields": descriptor.allowed_fields, "authentication": descriptor.authentication}]


def readiness(conn, person_id: str, fields: list[str]) -> dict:
    known = {r["attribute"] for r in conn.execute("SELECT DISTINCT attribute FROM claims WHERE person_id=? AND status='ACTIVE'", (person_id,)).fetchall()}
    missing = [field for field in fields if field not in known]
    conflicts = [r["attribute"] for r in conn.execute("SELECT attribute FROM conflicts WHERE person_id=? AND state IN ('OPEN','UNDER_REVIEW','DISPUTED')", (person_id,)).fetchall()]
    conflicted = [field for field in fields if field in conflicts]
    return {"required_fields": fields, "missing_fields": missing, "conflicted_fields": conflicted,
            "ready": not missing and not conflicted, "status": "READY" if not missing and not conflicted else "NEEDS_INFORMATION"}


@app.post("/v1/applications", status_code=201)
def create_application(service_id: str, request: Request, user: dict = Depends(csrf_guard)):
    with db.transaction() as conn:
        service = conn.execute("SELECT * FROM services WHERE id=? AND active=1", (service_id,)).fetchone()
        if not service:
            error("SERVICE_NOT_FOUND", "The selected service is unavailable.", "VALIDATION", 404)
        required = json.loads(service["required_fields_json"])
        result = readiness(conn, user["person_id"], required)
        application_id = identifier()
        status = "PREPARED" if result["ready"] else "INCOMPLETE"
        conn.execute("INSERT INTO applications(id,person_id,service_id,status,readiness_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                     (application_id, user["person_id"], service_id, status, json.dumps(result), iso(), iso()))
        audit.record(conn, actor=user["account_id"], action="APPLICATION_PREPARED", object_type="application", object_id=application_id,
                     correlation_id=request.state.correlation_id, result=status)
    return {"id": application_id, "service": service["name"], "organization": service["organization"], "adapter_mode": service["adapter_mode"], **result}


@app.get("/v1/applications")
def list_applications(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        rows = conn.execute("SELECT a.*,s.name service_name,s.adapter_mode FROM applications a JOIN services s ON s.id=a.service_id WHERE a.person_id=? ORDER BY a.created_at DESC", (user["person_id"],)).fetchall()
        return [{**dict(r), "readiness": json.loads(r["readiness_json"])} for r in rows]
    finally:
        conn.close()


def valid_expiry(value: str | None, *, max_hours: int) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if value else now() + timedelta(hours=max_hours)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed <= now() or parsed > now() + timedelta(hours=max_hours):
            raise ValueError
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, AttributeError):
        error("EXPIRY_INVALID", f"Expiry must be within the next {max_hours} hours.", "VALIDATION", 422)


@app.post("/v1/data-requests", status_code=201)
def create_data_request(body: RequestBody, request: Request, user: dict = Depends(csrf_guard)):
    if len(set(body.requested_fields)) != len(body.requested_fields) or not set(body.requested_fields) <= ALLOWED_FIELDS:
        error("FIELD_SCOPE_INVALID", "The request contains duplicate or unsupported fields.", "VALIDATION", 422)
    expires_at = valid_expiry(body.expires_at, max_hours=168)
    request_id, decision_id = identifier(), identifier()
    with db.transaction() as conn:
        service = conn.execute("SELECT * FROM services WHERE id=? AND active=1", (body.service_id,)).fetchone()
        if not service:
            error("SERVICE_NOT_FOUND", "The requesting service is not registered.", "POLICY_DENIED", 403)
        decision = policy.evaluate_data_request(requester=body.requester, registered_organization=service["organization"],
            requested_fields=body.requested_fields, contract_fields=json.loads(service["required_fields_json"]))
        outcome, reason = decision.outcome, decision.reason
        conn.execute("INSERT INTO policy_decisions(id,subject_person_id,action,outcome,reason,policy_version,created_at) VALUES(?,?,?,?,?,'v1',?)",
                     (decision_id, user["person_id"], "DATA_REQUEST", outcome, reason, iso()))
        status = "DENIED" if outcome == "DENY" else "AWAITING_CITIZEN_REVIEW"
        conn.execute("INSERT INTO data_requests(id,person_id,requester,purpose,legal_basis,requested_fields_json,service_id,expires_at,policy_outcome,policy_reason,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                     (request_id, user["person_id"], body.requester, body.purpose, body.legal_basis, json.dumps(body.requested_fields), service["id"], expires_at, outcome, reason, status, iso()))
        audit.record(conn, actor=user["account_id"], action="DATA_REQUEST_RECEIVED", object_type="data_request", object_id=request_id,
                     purpose=body.purpose, policy_decision_id=decision_id, correlation_id=request.state.correlation_id, result=outcome)
    return {"id": request_id, "requester": body.requester, "purpose": body.purpose,
            "requested_fields": body.requested_fields, "expires_at": expires_at,
            "policy": {"outcome": outcome, "reason": reason, "decision_id": decision_id}, "status": status,
            "adapter_mode": service["adapter_mode"]}


@app.get("/v1/data-requests")
def list_data_requests(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        rows = conn.execute("""SELECT r.*,c.id active_consent_id,c.scope_json active_consent_scope,c.status consent_status
            FROM data_requests r LEFT JOIN consents c ON c.request_id=r.id AND c.status='ACTIVE'
            WHERE r.person_id=? ORDER BY r.created_at DESC""", (user["person_id"],)).fetchall()
        return [{**dict(r), "requested_fields": json.loads(r["requested_fields_json"]),
                 "active_consent": ({"id": r["active_consent_id"], "scope": json.loads(r["active_consent_scope"]), "status": r["consent_status"]} if r["active_consent_id"] else None)} for r in rows]
    finally:
        conn.close()


@app.get("/v1/consents")
def list_consents(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        rows = conn.execute("SELECT id,request_id,requester,purpose,legal_basis,scope_json,presented_version,granted_at,expires_at,status FROM consents WHERE person_id=? ORDER BY granted_at DESC", (user["person_id"],)).fetchall()
        return [{**dict(r), "scope": json.loads(r["scope_json"])} for r in rows]
    finally:
        conn.close()


@app.post("/v1/data-requests/{request_id}/consents", status_code=201)
def grant_consent(request_id: str, body: ConsentBody, request: Request, user: dict = Depends(csrf_guard)):
    consent_id = identifier()
    with db.transaction() as conn:
        data_request = ensure_owner(conn, "data_requests", request_id, user["person_id"])
        if data_request["policy_outcome"] == "DENY":
            error("POLICY_DENIED", "Policy denied this request. Consent cannot override the denial.", "POLICY_DENIED", 403)
        requested = set(json.loads(data_request["requested_fields_json"]))
        if not body.fields or len(set(body.fields)) != len(body.fields) or not set(body.fields) <= requested:
            error("CONSENT_SCOPE_INVALID", "Granted fields must be a non-empty subset of the requested fields.", "VALIDATION", 422)
        expires_at = valid_expiry(body.expires_at or data_request["expires_at"], max_hours=168)
        if expires_at > data_request["expires_at"]:
            expires_at = data_request["expires_at"]
        granted_at = iso()
        conn.execute("UPDATE consents SET status='SUPERSEDED' WHERE request_id=? AND status='ACTIVE'", (request_id,))
        conn.execute("INSERT INTO consents(id,request_id,person_id,requester,purpose,legal_basis,scope_json,presented_version,granted_at,expires_at,status,auth_account_id) VALUES(?,?,?,?,?,?,?,?,?,?,'ACTIVE',?)",
                     (consent_id, request_id, user["person_id"], data_request["requester"], data_request["purpose"], data_request["legal_basis"], json.dumps(body.fields), "v1", granted_at, expires_at, user["account_id"]))
        conn.execute("UPDATE data_requests SET status='CONSENT_GRANTED' WHERE id=?", (request_id,))
        audit.record(conn, actor=user["account_id"], action="CONSENT_GRANTED", object_type="consent", object_id=consent_id,
                     purpose=data_request["purpose"], correlation_id=request.state.correlation_id,
                     after={"scope": body.fields, "expires_at": expires_at, "presentation_version": "v1"})
    return {"id": consent_id, "request_id": request_id, "scope": body.fields, "status": "ACTIVE", "expires_at": expires_at}


@app.post("/v1/consents/{consent_id}/revoke")
def revoke_consent(consent_id: str, request: Request, user: dict = Depends(csrf_guard)):
    with db.transaction() as conn:
        consent = ensure_owner(conn, "consents", consent_id, user["person_id"])
        if consent["status"] != "ACTIVE":
            error("CONSENT_INACTIVE", "This consent is not active.", "CONFLICT", 409)
        conn.execute("UPDATE consents SET status='REVOKED' WHERE id=?", (consent_id,))
        conn.execute("UPDATE data_requests SET status='CONSENT_REVOKED' WHERE id=?", (consent["request_id"],))
        audit.record(conn, actor=user["account_id"], action="CONSENT_REVOKED", object_type="consent", object_id=consent_id,
                     purpose=consent["purpose"], correlation_id=request.state.correlation_id)
    return {"id": consent_id, "status": "REVOKED", "future_transfers": "BLOCKED"}


def find_claim_value(conn, person_id: str, attribute: str):
    rows = conn.execute("SELECT value_json FROM claims WHERE person_id=? AND attribute=? AND status='ACTIVE'", (person_id, attribute)).fetchall()
    distinct = {r["value_json"] for r in rows}
    if len(distinct) != 1:
        return None
    return json.loads(next(iter(distinct)))


@app.post("/v1/transfers", status_code=201)
def transfer(request_id: str, consent_id: str, request: Request, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128), user: dict = Depends(csrf_guard)):
    transfer_id = identifier()
    with db.transaction() as conn:
        duplicate = conn.execute("SELECT request_id,receipt_json FROM transfers WHERE person_id=? AND idempotency_key=?", (user["person_id"], idempotency_key)).fetchone()
        if duplicate:
            if duplicate["request_id"] != request_id:
                error("IDEMPOTENCY_KEY_REUSED", "Use a new idempotency key for a different data request.", "CONFLICT", 409)
            return json.loads(duplicate["receipt_json"])
        control = conn.execute("SELECT value FROM platform_controls WHERE name='automation_state'").fetchone()["value"]
        if control == "STOPPED":
            return audited_denial(conn, user, request, "AUTOMATION_STOPPED", "STOP ALL AUTOMATION is active; outbound transfers are paused.",
                                  "POLICY_DENIED", 423, object_type="transfer", object_id=request_id)
        data_request = ensure_owner(conn, "data_requests", request_id, user["person_id"])
        if data_request["status"] == "TRANSFERRED":
            return audited_denial(conn, user, request, "REQUEST_ALREADY_TRANSFERRED", "This request has already been fulfilled. Create a new request for another transfer.",
                                  "CONFLICT", 409, object_type="data_request", object_id=request_id, purpose=data_request["purpose"])
        consent = ensure_owner(conn, "consents", consent_id, user["person_id"])
        if consent["request_id"] != request_id or consent["status"] != "ACTIVE" or consent["expires_at"] <= iso():
            return audited_denial(conn, user, request, "CONSENT_INVALID", "A matching active, unexpired consent is required.",
                                  "CONSENT_REQUIRED", 403, object_type="consent", object_id=consent_id)
        if data_request["expires_at"] <= iso() or data_request["policy_outcome"] == "DENY":
            return audited_denial(conn, user, request, "REQUEST_INVALID", "The request has expired or was denied by policy.",
                                  "POLICY_DENIED", 403, object_type="data_request", object_id=request_id, purpose=data_request["purpose"])
        scope = json.loads(consent["scope_json"])
        if not set(scope) <= set(json.loads(data_request["requested_fields_json"])):
            return audited_denial(conn, user, request, "CONSENT_SCOPE_INVALID", "Consent scope does not match the request.",
                                  "CONSENT_REQUIRED", 403, object_type="consent", object_id=consent_id, purpose=data_request["purpose"])
        values = {}
        for field in scope:
            if field in SENSITIVE_FIELDS:
                return audited_denial(conn, user, request, "HIGH_SENSITIVITY_REVIEW", "This reference adapter cannot send sensitive fields without an approved high-risk workflow.",
                                      "POLICY_DENIED", 403, object_type="consent", object_id=consent_id, purpose=data_request["purpose"])
            value = find_claim_value(conn, user["person_id"], field)
            if value is None:
                return audited_denial(conn, user, request, "FIELD_UNAVAILABLE", f"Field '{field}' is missing or conflicted.",
                                      "CONFLICT", 409, object_type="data_request", object_id=request_id, purpose=data_request["purpose"])
            values[field] = value
        service = conn.execute("SELECT * FROM services WHERE id=?", (data_request["service_id"],)).fetchone()
        if not service or service["adapter_mode"] != REFERENCE_ADAPTER.descriptor.mode:
            error("ADAPTER_UNAVAILABLE", "No production adapter is configured for this service.", "SOURCE_UNAVAILABLE", 503, retryable=True)
        try:
            adapter_result = REFERENCE_ADAPTER.submit(package=values, requested_fields=scope, transfer_id=transfer_id)
        except ValueError as exc:
            return audited_denial(conn, user, request, "ADAPTER_CONTRACT_REJECTED", str(exc),
                                  "SOURCE_UNAVAILABLE", 502, object_type="transfer", object_id=transfer_id,
                                  purpose=data_request["purpose"])
        policy_id = identifier()
        conn.execute("INSERT INTO policy_decisions(id,subject_person_id,action,outcome,reason,policy_version,created_at) VALUES(?,?,?,'ALLOW',?,'v1',?)",
                     (policy_id, user["person_id"], "DATA_TRANSFER", "Citizen-authenticated consent is active and every field is within the request scope.", iso()))
        receipt = {"transfer_id": transfer_id, "status": "COMPLETED", "adapter": {"id": adapter_result.adapter_id, "mode": adapter_result.mode,
                   "version": REFERENCE_ADAPTER.descriptor.version},
                   "recipient": data_request["requester"], "purpose": data_request["purpose"], "transferred_at": iso(),
                   "fields": list(adapter_result.accepted_fields), "source_references": [f"citizen-claim:{f}" for f in scope],
                   "adapter_reference": adapter_result.external_reference, "policy_decision_id": policy_id}
        conn.execute("INSERT INTO transfers(id,request_id,consent_id,person_id,adapter_id,adapter_mode,fields_json,package_json,receipt_json,idempotency_key,created_at) VALUES(?,?,?,?,?,'MOCK',?,?,?,?,?)",
                     (transfer_id, request_id, consent_id, user["person_id"], "reference-mock-v1", json.dumps(scope), json.dumps(values, ensure_ascii=False), json.dumps(receipt, ensure_ascii=False), idempotency_key, iso()))
        audit.record(conn, actor=user["account_id"], action="DATA_TRANSFER_COMPLETED", object_type="transfer", object_id=transfer_id,
                     purpose=data_request["purpose"], policy_decision_id=policy_id, correlation_id=request.state.correlation_id,
                     after={"recipient": data_request["requester"], "fields": scope, "adapter_mode": "MOCK"})
        conn.execute("INSERT INTO notifications(id,person_id,category,message,sensitive,created_at) VALUES(?,?, 'Transfer', ?,0,?)",
                     (identifier(), user["person_id"], f"A mock transfer receipt is ready for {data_request['requester']}.", iso()))
        conn.execute("UPDATE data_requests SET status='TRANSFERRED' WHERE id=?", (request_id,))
    return receipt


@app.get("/v1/transfers")
def list_transfers(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        rows = conn.execute("SELECT id,request_id,adapter_mode,receipt_json,created_at FROM transfers WHERE person_id=? ORDER BY created_at DESC", (user["person_id"],)).fetchall()
        return [{**dict(r), "receipt": json.loads(r["receipt_json"])} for r in rows]
    finally:
        conn.close()


@app.get("/v1/transfers/{transfer_id}/receipt")
def transfer_receipt(transfer_id: str, user: dict = Depends(user_context)):
    conn = request_db()
    try:
        row = conn.execute("SELECT receipt_json FROM transfers WHERE id=? AND person_id=?", (transfer_id, user["person_id"])).fetchone()
        if not row:
            error("NOT_FOUND", "The transfer receipt was not found.", "AUTHORIZATION", 404)
        return json.loads(row["receipt_json"])
    finally:
        conn.close()


@app.get("/v1/controls/automation")
def automation_status(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        return {"state": conn.execute("SELECT value FROM platform_controls WHERE name='automation_state'").fetchone()["value"], "scope": "GLOBAL", "can_transfer": conn.execute("SELECT value FROM platform_controls WHERE name='automation_state'").fetchone()["value"] == "RUNNING"}
    finally:
        conn.close()


@app.post("/v1/controls/automation/stop")
def stop_automation(request: Request, user: dict = Depends(csrf_guard)):
    with db.transaction() as conn:
        conn.execute("UPDATE platform_controls SET value='STOPPED',updated_at=?,updated_by=? WHERE name='automation_state'", (iso(), user["account_id"]))
        audit.record(conn, actor=user["account_id"], action="STOP_ALL_AUTOMATION", object_type="platform_control", object_id="automation_state", correlation_id=request.state.correlation_id)
    return {"state": "STOPPED", "scope": "GLOBAL"}


@app.post("/v1/controls/automation/resume")
def resume_automation(request: Request, control_key: str = Header(alias="X-Control-Key"), user: dict = Depends(csrf_guard)):
    configured = os.environ.get("TERRAVIA_CONTROL_KEY", "")
    if len(configured) < 32 or not safe_compare(digest(control_key), digest(configured)):
        error("CONTROL_AUTHORIZATION_REQUIRED", "A configured platform control key is required to resume outbound automation.", "AUTHORIZATION", 403)
    with db.transaction() as conn:
        conn.execute("UPDATE platform_controls SET value='RUNNING',updated_at=?,updated_by=? WHERE name='automation_state'", (iso(), user["account_id"]))
        audit.record(conn, actor=user["account_id"], action="AUTOMATION_RESUMED", object_type="platform_control", object_id="automation_state", correlation_id=request.state.correlation_id)
    return {"state": "RUNNING", "scope": "GLOBAL"}


@app.post("/v1/family/networks", status_code=201)
def create_family_network(body: NetworkBody, request: Request, user: dict = Depends(csrf_guard)):
    network_id = identifier()
    with db.transaction() as conn:
        conn.execute("INSERT INTO family_networks(id,owner_person_id,name,visibility,created_at) VALUES(?,?,?,'PRIVATE',?)", (network_id, user["person_id"], body.name, iso()))
        conn.execute("INSERT INTO family_members(network_id,person_id,role,joined_at) VALUES(?,?,'Family Custodian',?)", (network_id, user["person_id"], iso()))
        audit.record(conn, actor=user["account_id"], action="FAMILY_NETWORK_CREATED", object_type="family_network", object_id=network_id, correlation_id=request.state.correlation_id)
    return {"id": network_id, "name": body.name, "visibility": "PRIVATE", "domain": "FAMILY_HERITAGE"}


def own_network(conn, network_id: str, person_id: str):
    row = conn.execute("SELECT * FROM family_networks WHERE id=? AND owner_person_id=?", (network_id, person_id)).fetchone()
    if not row:
        error("NOT_FOUND", "The private family network was not found.", "AUTHORIZATION", 404)
    return dict(row)


@app.get("/v1/family/networks")
def list_family_networks(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        return [dict(r) for r in conn.execute("SELECT id,name,visibility,created_at FROM family_networks WHERE owner_person_id=?", (user["person_id"],)).fetchall()]
    finally:
        conn.close()


@app.post("/v1/family/networks/{network_id}/relationships", status_code=201)
def add_relationship(network_id: str, body: RelationshipBody, request: Request, user: dict = Depends(csrf_guard)):
    relationship_id = identifier()
    with db.transaction() as conn:
        own_network(conn, network_id, user["person_id"])
        conn.execute("INSERT INTO relationships(id,network_id,subject_person_id,related_label,relationship_type,evidence_level,state,visibility,created_at) VALUES(?,?,?,?,?,?,?,'FAMILY',?)",
                     (relationship_id, network_id, user["person_id"], body.related_label, body.relationship_type, body.evidence_level, body.state, iso()))
        audit.record(conn, actor=user["account_id"], action="FAMILY_RELATIONSHIP_RECORDED", object_type="relationship", object_id=relationship_id, correlation_id=request.state.correlation_id, result=body.evidence_level)
    return {"id": relationship_id, "state": body.state, "evidence_level": body.evidence_level, "grants_access": False}


@app.get("/v1/family/networks/{network_id}/relationships")
def list_relationships(network_id: str, user: dict = Depends(user_context)):
    conn = request_db()
    try:
        own_network(conn, network_id, user["person_id"])
        return [dict(r) for r in conn.execute("SELECT id,related_label,relationship_type,evidence_level,state,visibility,created_at FROM relationships WHERE network_id=?", (network_id,)).fetchall()]
    finally:
        conn.close()


@app.post("/v1/family/networks/{network_id}/items", status_code=201)
def add_family_item(network_id: str, body: FamilyItemBody, request: Request, user: dict = Depends(csrf_guard)):
    item_id = identifier()
    with db.transaction() as conn:
        own_network(conn, network_id, user["person_id"])
        conn.execute("INSERT INTO family_items(id,network_id,owner_person_id,item_type,title,content,evidence_level,certainty,visibility,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (item_id, network_id, user["person_id"], body.item_type, body.title, body.content, body.evidence_level, body.certainty, body.visibility, iso()))
        audit.record(conn, actor=user["account_id"], action="FAMILY_ITEM_ADDED", object_type=body.item_type.lower(), object_id=item_id,
                     correlation_id=request.state.correlation_id, result=body.certainty)
    return {"id": item_id, "type": body.item_type, "certainty": body.certainty, "visibility": body.visibility}


@app.get("/v1/family/networks/{network_id}/items")
def list_family_items(network_id: str, user: dict = Depends(user_context)):
    conn = request_db()
    try:
        own_network(conn, network_id, user["person_id"])
        return [dict(r) for r in conn.execute("SELECT id,item_type,title,evidence_level,certainty,visibility,created_at FROM family_items WHERE network_id=?", (network_id,)).fetchall()]
    finally:
        conn.close()


@app.post("/v1/life-events", status_code=201)
def propose_life_event(body: LifeEventBody, request: Request, user: dict = Depends(csrf_guard)):
    event_id = identifier()
    impacts = [{"domain": domain, "action": "REVIEW_RECOMMENDATION", "automatic_mutation": False} for domain in body.affected_domains]
    with db.transaction() as conn:
        for evidence_id in body.evidence_references:
            conn.execute("SELECT id FROM evidence WHERE id=? AND person_id=?", (evidence_id, user["person_id"])).fetchone() or error("EVIDENCE_NOT_FOUND", "An evidence reference was not found.", "VALIDATION", 422)
        conn.execute("INSERT INTO life_events(id,person_id,event_type,occurred_range,evidence_json,risk,state,impact_json,created_at,updated_at) VALUES(?,?,?,?,?,?,'PROPOSED',?,?,?)",
                     (event_id, user["person_id"], body.event_type, body.occurred_range, json.dumps(body.evidence_references), body.risk, json.dumps(impacts), iso(), iso()))
        audit.record(conn, actor=user["account_id"], action="LIFE_EVENT_PROPOSED", object_type="life_event", object_id=event_id, correlation_id=request.state.correlation_id, result="HUMAN_REVIEW")
    return {"id": event_id, "state": "PROPOSED", "risk": body.risk, "impact_analysis": impacts, "automatic_mutations": False}


@app.get("/v1/life-events")
def list_life_events(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        rows = conn.execute("SELECT * FROM life_events WHERE person_id=? ORDER BY created_at DESC", (user["person_id"],)).fetchall()
        return [{**dict(r), "evidence_references": json.loads(r["evidence_json"]), "impact_analysis": json.loads(r["impact_json"])} for r in rows]
    finally:
        conn.close()


@app.post("/v1/life-events/{event_id}/review")
def review_life_event(event_id: str, decision: Literal["UNDER_REVIEW", "DISPUTED", "CANCELLED"], request: Request, user: dict = Depends(csrf_guard)):
    with db.transaction() as conn:
        event = ensure_owner(conn, "life_events", event_id, user["person_id"])
        if event["state"] not in {"PROPOSED", "EVIDENCE_REQUIRED", "UNDER_REVIEW"}:
            error("EVENT_STATE_INVALID", "This event cannot enter the requested review state.", "CONFLICT", 409)
        conn.execute("UPDATE life_events SET state=?,updated_at=? WHERE id=?", (decision, iso(), event_id))
        audit.record(conn, actor=user["account_id"], action="LIFE_EVENT_REVIEWED", object_type="life_event", object_id=event_id, correlation_id=request.state.correlation_id, result=decision)
    return {"id": event_id, "state": decision, "domain_mutations": []}


@app.post("/v1/legacy/vault", status_code=201)
def create_legacy_vault(request: Request, user: dict = Depends(csrf_guard)):
    with db.transaction() as conn:
        row = conn.execute("SELECT * FROM legacy_vaults WHERE owner_person_id=?", (user["person_id"],)).fetchone()
        if row:
            return {"id": row["id"], "status": row["status"]}
        vault_id = identifier()
        conn.execute("INSERT INTO legacy_vaults(id,owner_person_id,status,created_at) VALUES(?,?,'ACTIVE',?)", (vault_id, user["person_id"], iso()))
        audit.record(conn, actor=user["account_id"], action="LEGACY_VAULT_CREATED", object_type="legacy_vault", object_id=vault_id, correlation_id=request.state.correlation_id)
    return {"id": vault_id, "status": "ACTIVE", "custodian_is_steward": True}


@app.get("/v1/legacy/vault")
def get_legacy_vault(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        vault = conn.execute("SELECT * FROM legacy_vaults WHERE owner_person_id=?", (user["person_id"],)).fetchone()
        if not vault:
            return {"status": "NOT_CREATED", "release_available": False}
        items = conn.execute("SELECT id,title,classification,release_mode,trigger_type,custodians_json,released_at,created_at FROM legacy_items WHERE vault_id=?", (vault["id"],)).fetchall()
        return {"id": vault["id"], "status": vault["status"], "items": [{**dict(r), "custodians": json.loads(r["custodians_json"])} for r in items], "release_available": False}
    finally:
        conn.close()


@app.post("/v1/legacy/items", status_code=201)
def add_legacy_item(body: LegacyItemBody, request: Request, user: dict = Depends(csrf_guard)):
    item_id = identifier()
    with db.transaction() as conn:
        vault = conn.execute("SELECT * FROM legacy_vaults WHERE owner_person_id=?", (user["person_id"],)).fetchone()
        if not vault:
            error("VAULT_REQUIRED", "Create a legacy vault before adding an item.", "VALIDATION", 409)
        conn.execute("INSERT INTO legacy_items(id,vault_id,owner_person_id,title,content,classification,release_mode,trigger_type,custodians_json,created_at) VALUES(?,?,?,?,?,?,?,'EXPLICIT_VERIFIED_TRIGGER',?,?)",
                     (item_id, vault["id"], user["person_id"], body.title, body.content, body.classification, body.release_mode, json.dumps(body.custodians), iso()))
        audit.record(conn, actor=user["account_id"], action="LEGACY_ITEM_CREATED", object_type="legacy_item", object_id=item_id, correlation_id=request.state.correlation_id, result="PRIVATE")
    return {"id": item_id, "status": "PRIVATE", "trigger_type": "EXPLICIT_VERIFIED_TRIGGER", "death_inferred": False}


@app.get("/v1/notifications")
def list_notifications(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        rows = conn.execute("SELECT id,category,message,sensitive,acknowledged_at,created_at FROM notifications WHERE person_id=? ORDER BY created_at DESC", (user["person_id"],)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/v1/audit")
def list_audit(user: dict = Depends(user_context)):
    conn = request_db()
    try:
        rows = conn.execute("SELECT timestamp,actor,action,object_type,object_id,purpose,result,correlation_id,event_hash,previous_hash FROM audit_events WHERE actor=? ORDER BY rowid DESC LIMIT 200", (user["account_id"],)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.post("/v1/assistant/explain")
async def explain(request: Request, user: dict = Depends(csrf_guard)):
    """Optional Ollama explanation using non-sensitive workflow status only."""
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "")
    if not model:
        error("AI_UNAVAILABLE", "No Ollama model is configured. The governed service remains available without AI.", "SOURCE_UNAVAILABLE", 503, retryable=True)
    endpoint = urllib.parse.urlparse(base)
    if endpoint.scheme != "http" or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"} or endpoint.username or endpoint.password:
        error("AI_CONFIGURATION_INVALID", "Ollama must be configured on this machine over loopback HTTP.", "VALIDATION", 503)
    conn = request_db()
    try:
        counts = {"open_conflicts": conn.execute("SELECT count(*) FROM conflicts WHERE person_id=? AND state IN ('OPEN','UNDER_REVIEW','DISPUTED')", (user["person_id"],)).fetchone()[0],
                  "applications": conn.execute("SELECT count(*) FROM applications WHERE person_id=?", (user["person_id"],)).fetchone()[0],
                  "pending_requests": conn.execute("SELECT count(*) FROM data_requests WHERE person_id=? AND status='AWAITING_CITIZEN_REVIEW'", (user["person_id"],)).fetchone()[0]}
    finally:
        conn.close()
    payload = json.dumps({"model": model, "stream": False, "messages": [
        {"role": "system", "content": "Explain TerraVia workflow status in plain language. You are non-authoritative. Never recommend bypassing consent, policy, human review, or STOP ALL AUTOMATION. Do not infer identity or legal facts."},
        {"role": "user", "content": f"Explain this non-sensitive workflow summary: {json.dumps(counts)}. Do not ask for private identity data."}]})
    def call_ollama():
        req = urllib.request.Request(base + "/api/chat", data=payload.encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    try:
        result = await asyncio.to_thread(call_ollama)
        message = result.get("message", {}).get("content", "")
        if not message:
            error("AI_RESPONSE_INVALID", "The configured Ollama service returned no explanation.", "SOURCE_UNAVAILABLE", 502, retryable=True)
        with db.transaction() as tx:
            audit.record(tx, actor=user["account_id"], action="AI_EXPLANATION_REQUESTED", object_type="assistant", correlation_id=request.state.correlation_id, result="NON_AUTHORITATIVE")
        return {"status": "available", "provider": "OLLAMA", "model": model, "label": "SUGGESTED", "authoritative": False, "text": message}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        error("AI_UNAVAILABLE", "The configured Ollama service did not respond. No workflow action was taken.", "SOURCE_UNAVAILABLE", 503, retryable=True)
