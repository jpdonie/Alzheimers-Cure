"""Per-session locking: model calls run outside the session lock, and late replies never overwrite newer state."""
import os
os.environ["APPRENTICE_OFFLINE"] = "1"
os.environ["APPRENTICE_COOLDOWN"] = "0"
import threading, time
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


SLOW = 3.0   # seconds the mocked vision provider sleeps; only the provider is mocked, every lock is the real one


def test_slow_frame_does_not_block_question(monkeypatch):
    h, ev = start("slow-frame")
    entered = threading.Event()
    def vision(data_url, prompt):
        entered.set(); time.sleep(SLOW); return "Confirmed: PRN selected."
    monkeypatch.setattr(llm, "vision", vision)
    with ThreadPoolExecutor(2) as pool:
        t0 = time.monotonic()
        frame = pool.submit(c.post, "/frames", json={"event_id": ev["id"], "data_url": PNG + "AAAA"}, headers=h)
        assert entered.wait(5)                                    # /frames is now inside the vision call
        q = c.post("/question", json={"event_id": ev["id"], "signals": OK}, headers=h)
        q_took = time.monotonic() - t0
        assert q.status_code == 200 and q.json()["question"]["event_id"] == ev["id"]
        assert q_took < 1.0, f"/question waited {q_took:.2f}s for vision"
        assert not frame.done()                                   # vision really was still running
        assert frame.result(timeout=SLOW + 5).json() == {"ok": True, "vision": "Confirmed: PRN selected."}
        assert time.monotonic() - t0 >= SLOW


def test_late_slow_frame_never_overwrites_fast_newer_frame(monkeypatch):
    h, ev = start("two-frames")
    older_entered = threading.Event()
    def vision(data_url, prompt):
        if data_url.endswith("OLD="):
            older_entered.set(); time.sleep(SLOW); return "Confirmed: older frame."
        return "Confirmed: newer frame."
    monkeypatch.setattr(llm, "vision", vision)
    with ThreadPoolExecutor(1) as pool:
        t0 = time.monotonic()
        older = pool.submit(c.post, "/frames", json={"event_id": ev["id"], "data_url": PNG + "OLD="}, headers=h)   # frame 1, slow
        assert older_entered.wait(5)
        newer = c.post("/frames", json={"event_id": ev["id"], "data_url": PNG + "NEW="}, headers=h)                # frame 2, fast
        assert newer.json()["vision"] == "Confirmed: newer frame." and time.monotonic() - t0 < 1.0
        assert older.result(timeout=SLOW + 5).json() == {"ok": True, "vision": None}   # late reply for frame 1 is dropped
    s = api.SESSIONS["two-frames"]
    assert s.ev(ev["id"])["vision"] == "Confirmed: newer frame." and s.frames[ev["id"]] == PNG + "NEW="
    assert s.vision_pending == 0


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
