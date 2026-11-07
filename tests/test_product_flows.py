import json
import os

from conftest import csrf


def test_identity_conflict_is_cased_without_overwrite(signed_in):
    client, person_id = signed_in
    first = client.post("/v1/claims", headers=csrf(client), json={"attribute": "date_of_birth", "value": "1990-01-01"})
    second = client.post("/v1/claims", headers=csrf(client), json={"attribute": "date_of_birth", "value": "1991-01-01"})
    assert first.status_code == second.status_code == 201
    assert second.json()["conflict_id"]
    conflict = client.get("/v1/conflicts").json()[0]
    assert conflict["state"] == "OPEN"
    assert len(conflict["claim_ids"]) == 2
    review = client.post(f"/v1/conflicts/{conflict['id']}/review", headers=csrf(client))
    assert review.json()["state"] == "UNDER_REVIEW"
    data = client.get(f"/v1/persons/{person_id}").json()
    assert len(data["claims"]) == 2
    assert all(c["verification_status"] == "UNVERIFIED" for c in data["claims"])


def test_consent_minimization_stop_and_mock_transfer(signed_in):
    client, person_id = signed_in
    for name, value in (("name", "A Citizen"), ("email", "citizen@example.test"), ("qualification", "Engineering")):
        response = client.post("/v1/claims", headers=csrf(client), json={"attribute": name, "value": value})
        assert response.status_code == 201
    service = next(s for s in client.get("/v1/services").json() if s["id"] == "svc-reference-qualification")
    request = client.post("/v1/data-requests", headers=csrf(client), json={
        "requester": service["organization"], "purpose": "Review this qualification", "legal_basis": "CONSENT",
        "requested_fields": ["name", "email", "qualification"], "service_id": service["id"]})
    assert request.status_code == 201
    request_id = request.json()["id"]
    consent = client.post(f"/v1/data-requests/{request_id}/consents", headers=csrf(client), json={"fields": ["name", "qualification"]})
    assert consent.status_code == 201
    consent_id = consent.json()["id"]
    stopped = client.post(f"/v1/transfers?request_id={request_id}&consent_id={consent_id}", headers={**csrf(client), "Idempotency-Key": "test-stop-key-0001"})
    assert stopped.status_code == 423
    resume = client.post("/v1/controls/automation/resume", headers={**csrf(client), "X-Control-Key": os.environ["TERRAVIA_CONTROL_KEY"]})
    assert resume.status_code == 200
    sent = client.post(f"/v1/transfers?request_id={request_id}&consent_id={consent_id}", headers={**csrf(client), "Idempotency-Key": "test-transfer-key-0001"})
    assert sent.status_code == 201, sent.text
    assert sent.json()["adapter"]["mode"] == "MOCK"
    assert sent.json()["fields"] == ["name", "qualification"]
    assert client.get(f"/v1/transfers/{sent.json()['transfer_id']}/receipt").json()["fields"] == ["name", "qualification"]
    duplicate = client.post(f"/v1/transfers?request_id={request_id}&consent_id={consent_id}", headers={**csrf(client), "Idempotency-Key": "test-transfer-key-0001"})
    assert duplicate.status_code == 201
    assert duplicate.json()["transfer_id"] == sent.json()["transfer_id"]
    conn = __import__("terravia.db", fromlist=["connect"]).connect()
    try:
        row = conn.execute("SELECT package_json FROM transfers WHERE id=?", (sent.json()["transfer_id"],)).fetchone()
        assert set(json.loads(row["package_json"])) == {"name", "qualification"}
        assert conn.execute("SELECT value FROM platform_controls WHERE name='automation_state'").fetchone()["value"] == "RUNNING"
        assert conn.execute("SELECT count(*) FROM audit_events WHERE result='AUTOMATION_STOPPED'").fetchone()[0] == 1
    finally:
        conn.close()
    assert client.get("/v1/me").json()["person_id"] == person_id


def test_revoked_consent_blocks_transfer(signed_in):
    client, _ = signed_in
    client.post("/v1/claims", headers=csrf(client), json={"attribute": "name", "value": "Citizen"})
    service = client.get("/v1/services").json()[0]
    request = client.post("/v1/data-requests", headers=csrf(client), json={"requester": service["organization"], "purpose": "Review contact", "legal_basis": "CONSENT", "requested_fields": ["name"], "service_id": service["id"]}).json()
    consent = client.post(f"/v1/data-requests/{request['id']}/consents", headers=csrf(client), json={"fields": ["name"]}).json()
    revoked = client.post(f"/v1/consents/{consent['id']}/revoke", headers=csrf(client))
    assert revoked.json()["status"] == "REVOKED"
    client.post("/v1/controls/automation/resume", headers={**csrf(client), "X-Control-Key": os.environ["TERRAVIA_CONTROL_KEY"]})
    denied = client.post(f"/v1/transfers?request_id={request['id']}&consent_id={consent['id']}", headers={**csrf(client), "Idempotency-Key": "revoked-consent-key"})
    assert denied.status_code == 403


def test_family_relationship_does_not_grant_access(signed_in):
    client, _ = signed_in
    network = client.post("/v1/family/networks", headers=csrf(client), json={"name": "Private family"}).json()
    relationship = client.post(f"/v1/family/networks/{network['id']}/relationships", headers=csrf(client), json={
        "related_label": "Grandparent", "relationship_type": "grandparent", "evidence_level": "LIVING_MEMORY"})
    assert relationship.status_code == 201
    assert relationship.json()["grants_access"] is False
    assert client.get(f"/v1/family/networks/{network['id']}/relationships").status_code == 200
    other = client.post("/v1/auth/register", json={"email": "other@example.test", "password": "a-different-password-123"})
    assert other.status_code == 201
    denied = client.get(f"/v1/family/networks/{network['id']}/relationships")
    assert denied.status_code == 404


def test_life_event_never_cascades_and_legacy_has_no_inactivity_release(signed_in):
    client, _ = signed_in
    event = client.post("/v1/life-events", headers=csrf(client), json={"event_type": "marriage", "risk": "HIGH", "affected_domains": ["passport", "employer"]})
    assert event.status_code == 201
    assert event.json()["automatic_mutations"] is False
    assert all(i["automatic_mutation"] is False for i in event.json()["impact_analysis"])
    vault = client.post("/v1/legacy/vault", headers=csrf(client))
    assert vault.status_code == 201
    item = client.post("/v1/legacy/items", headers=csrf(client), json={"title": "Family note", "content": "Private", "classification": "L3"})
    assert item.status_code == 201
    assert item.json()["death_inferred"] is False
    state = client.get("/v1/legacy/vault").json()
    assert state["release_available"] is False
    assert state["items"][0]["trigger_type"] == "EXPLICIT_VERIFIED_TRIGGER"


def test_audit_is_append_only_and_reports_security_events(signed_in):
    client, _ = signed_in
    events = client.get("/v1/audit").json()
    assert any(e["action"] == "PERSON_CREATED" for e in events)
    conn = __import__("terravia.db", fromlist=["connect"]).connect()
    try:
        event_id = conn.execute("SELECT id FROM audit_events LIMIT 1").fetchone()["id"]
        try:
            conn.execute("DELETE FROM audit_events WHERE id=?", (event_id,))
            assert False, "audit deletion should fail"
        except Exception as exc:
            assert "append-only" in str(exc)
    finally:
        conn.close()


def test_readiness_and_web_shell_are_real_routes(signed_in):
    client, _ = signed_in
    home = client.get("/")
    assert home.status_code == 200
    assert "TerraVia Citizen Service" in home.text
    assert client.get("/static/app.js").status_code == 200
    service_id = "svc-reference-qualification"
    incomplete = client.post(f"/v1/applications?service_id={service_id}", headers=csrf(client), json={})
    assert incomplete.status_code == 201
    assert incomplete.json()["status"] == "NEEDS_INFORMATION"
    assert set(incomplete.json()["missing_fields"]) == {"name", "email", "qualification"}
    for field, value in (("name", "Citizen"), ("email", "citizen@example.test"), ("qualification", "Engineering")):
        client.post("/v1/claims", headers=csrf(client), json={"attribute": field, "value": value})
    ready = client.post(f"/v1/applications?service_id={service_id}", headers=csrf(client), json={})
    assert ready.json()["status"] == "READY"
    assert ready.json()["ready"] is True


def test_mutations_require_csrf_and_validation_is_structured(signed_in):
    client, _ = signed_in
    denied = client.post("/v1/claims", json={"attribute": "name", "value": "Citizen"})
    assert denied.status_code == 403
    assert denied.json()["error"]["category"] == "AUTHORIZATION"
    invalid = client.post("/v1/auth/register", json={"email": "bad-email", "password": "a-strong-password-123"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_FAILED"
