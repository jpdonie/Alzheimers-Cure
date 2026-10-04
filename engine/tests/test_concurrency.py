"""Per-session locking: model calls run outside the session lock, and late replies never overwrite newer state."""
import os
os.environ["APPRENTICE_OFFLINE"] = "1"
os.environ["APPRENTICE_COOLDOWN"] = "0"
import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from engine import api, llm

c = TestClient(api.app)
OK = {"voice_silent": True, "hands_still": True, "screen_stable": True}
PNG = "data:image/png;base64,"


def start(sid):
    h = {"x-session-id": sid}
    assert c.post("/session", json={"mode": "capture"}, headers=h).status_code == 200
    ev = c.post("/events", json={"field": "intervention", "value": "give_prn_medication", "form": {}}, headers=h).json()["event"]
    return h, ev


def test_slow_frame_does_not_block_question(monkeypatch):
    h, ev = start("slow-frame")
    entered, release = threading.Event(), threading.Event()
    def vision(data_url, prompt):
        entered.set(); release.wait(10); return "Confirmed: PRN selected."
    monkeypatch.setattr(llm, "vision", vision)
    with ThreadPoolExecutor(2) as pool:
        frame = pool.submit(c.post, "/frames", json={"event_id": ev["id"], "data_url": PNG + "AAAA"}, headers=h)
        assert entered.wait(5)
        q = pool.submit(c.post, "/question", json={"event_id": ev["id"], "signals": OK}, headers=h).result(timeout=5)
        assert q.status_code == 200 and q.json()["question"]["event_id"] == ev["id"]   # answered while vision is still running
        assert not frame.done()
        release.set()
        assert frame.result(timeout=5).json() == {"ok": True, "vision": "Confirmed: PRN selected."}


def test_older_vision_reply_never_overwrites_newer(monkeypatch):
    h, ev = start("two-frames")
    older_entered, release_older = threading.Event(), threading.Event()
    def vision(data_url, prompt):
        if data_url.endswith("OLD="):
            older_entered.set(); release_older.wait(10); return "Confirmed: older frame."
        return "Confirmed: newer frame."
    monkeypatch.setattr(llm, "vision", vision)
    with ThreadPoolExecutor(2) as pool:
        older = pool.submit(c.post, "/frames", json={"event_id": ev["id"], "data_url": PNG + "OLD="}, headers=h)
        assert older_entered.wait(5)
        newer = c.post("/frames", json={"event_id": ev["id"], "data_url": PNG + "NEW="}, headers=h)
        assert newer.json()["vision"] == "Confirmed: newer frame."
        release_older.set()
        assert older.result(timeout=5).json() == {"ok": True, "vision": None}   # stale reply dropped
    s = api.SESSIONS["two-frames"]
    assert s.ev(ev["id"])["vision"] == "Confirmed: newer frame." and s.frames[ev["id"]] == PNG + "NEW="


def test_off_record_during_vision_drops_the_caption(monkeypatch):
    h, ev = start("off-record-frame")
    entered, release = threading.Event(), threading.Event()
    def vision(data_url, prompt):
        entered.set(); release.wait(10); return "Confirmed: PRN selected."
    monkeypatch.setattr(llm, "vision", vision)
    with ThreadPoolExecutor(1) as pool:
        frame = pool.submit(c.post, "/frames", json={"event_id": ev["id"], "data_url": PNG + "AAAA"}, headers=h)
        assert entered.wait(5)
        assert c.post("/off-record", json={"since_ts": 0}, headers=h).json()["events"] == 1
        release.set()
        assert frame.result(timeout=5).json()["vision"] is None
    s = api.SESSIONS["off-record-frame"]
    assert s.events == [] and s.frames == {}
