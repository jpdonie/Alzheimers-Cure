import os
os.environ["APPRENTICE_OFFLINE"] = "1"
os.environ["APPRENTICE_COOLDOWN"] = "0"
from fastapi.testclient import TestClient
from engine.api import app

c = TestClient(app)
OK = {"voice_silent": True, "hands_still": True, "screen_stable": True}


def test_contract_capture_to_teach_through_http():
    assert c.post("/session", json={"mode": "capture"}).status_code == 200
    e = c.post("/events", json={"field": "intervention", "value": "give_prn_medication", "form": {}}).json()["event"]
    q = c.post("/question", json={"event_id": e["id"], "signals": OK}).json()["question"]
    assert q["event_id"] == e["id"] and q["text"].startswith("I saw you")
    a = c.post("/answer", json={"question_id": q["id"], "text": "Never alone; the nurse decides."}).json()
    assert a["transition"]["after"] in ("expert_stated", "confirmed")
    wm1 = c.get("/workmap").json(); assert wm1["schema"] == "workmap/1" and wm1["steps"]
    c.post("/debrief/confirm", json={"rule_id": wm1["steps"][0]["rule_id"], "ok": True})
    assert c.get("/workmap").json()["map_version"] != wm1["map_version"]          # teach-back changes the artifact
    assert c.post("/session", json={"mode": "teach"}).status_code == 200            # teach reuses the learned map
    opened = c.post("/teach/open", json={"case_id": "T3"}).json()
    assert opened["map_version"] == c.get("/workmap").json()["map_version"] and "rule_ids" not in opened
    blocked = c.post("/teach/check-save", json={"case_id": "T3", "form": {"incident_type": "refusal_of_care", "intervention": "give_prn_medication", "escalate_to": "none", "checks": ["pain"]}}).json()
    assert not blocked["saved"] and blocked["blocked"][0]["guardrail_id"] == "R4-treatment-routing" and blocked["blocked"][0]["trace"]


def test_boundary_validation_and_unknown_ids():
    assert c.post("/session", json={"mode": "bogus"}).status_code == 422
    assert c.post("/answer", json={"question_id": "nope", "text": "x"}).status_code == 404
    assert c.post("/answer", json={"question_id": "nope", "text": ""}).status_code == 422
    assert c.post("/off-record", json={"since_ts": -1}).status_code == 422
    assert c.post("/frames", json={"event_id": "E-x", "data_url": "http://evil/x.png"}).status_code == 422
    assert c.post("/teach/open", json={"case_id": "T99"}).status_code == 404
    assert c.get("/frame/E-missing").status_code == 404


def test_cors_only_allows_local_web_origin():
    ok = c.options("/events", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    bad = c.options("/events", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers
