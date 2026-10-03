"""Instrumented timed rehearsal (opt-in, REHEARSAL=1, spends a few provider credits): runs the documented demo script with
voice connected (fake mic), the tab shared and a live LLM, checks every mandatory challenge behaviour and writes data/rehearsal_report.json.
Engine: live mode, default-ish cooldown (APPRENTICE_COOLDOWN=8). Web on :3000."""
import json, os, re, time, urllib.request, pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(os.getenv("REHEARSAL") != "1", reason="opt-in")
WEB, ENG = "http://localhost:3000", "http://localhost:8000"
OUT = Path(__file__).resolve().parent.parent / "data"


def test_timed_rehearsal():
    t0 = time.time(); log = []
    def ok(name, cond, detail=""):
        log.append({"t": round(time.time() - t0, 1), "behaviour": name, "pass": bool(cond), "detail": detail}); assert cond, name
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--auto-accept-this-tab-capture"])
        ctx = b.new_context(permissions=["microphone"], viewport={"width": 1440, "height": 1000}); pg = ctx.new_page()
        pg.goto(f"{WEB}/capture"); pg.get_by_text("Your task (fake data)").wait_for()
        pg.get_by_role("button", name="Start voice").click(); pg.get_by_role("button", name="Voice connected").wait_for(timeout=20000)
        pg.get_by_role("button", name="Share screen").click(); pg.get_by_text("Sharing this tab").wait_for(timeout=10000)
        ok("voice agent connected and tab shared", True)

        obs = pg.get_by_label("What you observed (facts only)")
        for _ in range(7): obs.type("refuses tray ", delay=150); pg.wait_for_timeout(250)
        ok("stays silent while the expert types", pg.locator("[role=status]").count() == 0)

        qs = []
        def ask_and_answer(label, answer, first=False):
            pg.locator("[role=status]").wait_for(timeout=30000); txt = pg.locator("[role=status]").inner_text()
            qs.append(txt); 
            if first: pg.get_by_text("Asking", exact=True).wait_for(timeout=20000)   # ElevenAgents is voicing the engine question
            pg.get_by_placeholder("Answer by voice, or type here").fill(answer); pg.get_by_role("button", name="Send answer").click()
            pg.get_by_text("Learned:").wait_for(timeout=20000)
        pg.get_by_label("Pain / physical discomfort").check()
        ask_and_answer("q1", "Pain first. If she cannot tell me and looks frightened I call the nurse before anything else.", first=True)
        ok("agent voiced the question (ElevenAgents speaking)", True)
        pg.get_by_label("Intervention").select_option("give_prn_medication")
        ask_and_answer("q2", "I would never decide that myself; it always goes to the nurse.")
        pg.get_by_label("Escalate to").select_option("nurse")
        ask_and_answer("q3", "The nurse takes it to the coordinating physician.")
        ok(">=3 questions, each citing a visible screen event", len(qs) >= 3 and all(q.startswith("I saw you") for q in qs), " | ".join(qs))
        ok(">=1 guardrail question", pg.get_by_text("guardrail:", exact=False).count() >= 1)
        events = json.load(urllib.request.urlopen(ENG + "/health"))  # engine alive
        pg.screenshot(path=str(OUT / "rehearsal_1_capture.png"))

        pg.get_by_role("link", name="Task finished → Debrief").click(); pg.get_by_text("what I am still unsure about").wait_for()
        for _ in range(3):
            pg.get_by_placeholder("Answer by voice, or type").fill("It depends on the resident; when unsure I ask the nurse."); pg.get_by_role("button", name="Send answer").click(); pg.wait_for_timeout(1500)
        ok(">=3 genuinely new debrief questions answered", pg.get_by_text("✓ at least 3 new follow-ups answered").count() == 1)
        pg.get_by_role("button", name="Explain the process back to me").click(); pg.get_by_role("button", name="Yes, that is it").first.wait_for()
        n = pg.get_by_role("button", name="Yes, that is it").count()
        pg.get_by_placeholder("Correct it: what is missing or wrong?").first.fill("Also check hearing aids and glasses before assuming refusal.")
        pg.get_by_role("button", name="Correct it").first.click()
        for i in range(1, n): pg.get_by_role("button", name="Yes, that is it").nth(i).click(); pg.wait_for_timeout(400)
        pg.get_by_text("correction saved as an expert exception").first.wait_for()
        ok("teach-back with one expert correction and confirmations", pg.get_by_text("confirmed by expert").count() >= n - 1)
        pg.screenshot(path=str(OUT / "rehearsal_2_debrief.png"), full_page=True)

        pg.get_by_role("link", name="See the Work Map →").click(); pg.get_by_text("In the expert's words (live)").wait_for()
        ok("Work Map step shows frame, live expert words, guardrail, facets",
           pg.locator("img[alt='Captured screen moment']").count() >= 1 and pg.get_by_text("Pain first").count() >= 1 and pg.get_by_text("Guardrails").count() >= 1 and pg.get_by_text("evidence:", exact=False).count() >= 1)
        pg.get_by_text("Provenance").first.click()
        ok("provenance separates screen moment from transcript", pg.get_by_text("screen moment").count() >= 1 and pg.get_by_text("transcript").count() >= 1)
        pg.screenshot(path=str(OUT / "rehearsal_3_map.png"), full_page=True)

        pg.get_by_role("link", name="Teach a new hire →").click(); pg.get_by_text("Predict:").wait_for()
        pg.get_by_role("button", name="Start voice").click(); pg.get_by_role("button", name="Voice connected").wait_for(timeout=20000)
        pg.get_by_role("button", name=re.compile(r"^A\. Note")).click()
        pg.get_by_role("button", name="Save record").click(); pg.get_by_text("Hold on: not saved yet").wait_for()
        ok("wrong decision on an unseen case is stopped before Save, with guardrail, matched fields, predicate, expert words",
           pg.get_by_text("guardrail R1-somatic-first").count() == 1 and pg.get_by_text("predicate:", exact=False).count() >= 1 and pg.locator(".quote").count() >= 1)
        ok("replays the expert's live screen moment", pg.locator("img[alt='Expert screen moment']").count() >= 1)
        pg.screenshot(path=str(OUT / "rehearsal_4_teach_block.png"))
        pg.get_by_role("button", name="Fix it").click()
        pg.get_by_label("Pain / physical discomfort").check(); pg.get_by_label("Escalate to").select_option("team_meeting")
        pg.get_by_label("Intervention").select_option("swap_carer_or_call_psychologist"); pg.get_by_label("Behaviour is").select_option("new")
        pg.get_by_role("button", name="Save record").click(); pg.get_by_text("Saved. Mastery so far").wait_for()
        ok("retry succeeds; mastery summary and next scenario shown", pg.get_by_text("Next scenario:", exact=False).count() == 1)

        def post(path, body):
            r = urllib.request.Request(ENG + path, json.dumps(body).encode(), {"content-type": "application/json", "x-session-id": "rehearsal-probe"})
            try: return urllib.request.urlopen(r).status
            except urllib.error.HTTPError as e: return e.code
        post("/recording", {"on": False}); ok("Off the record: server refuses late writes", post("/events", {"field": "checks", "value": []}) == 409)
        b.close()
    total = round(time.time() - t0, 1)
    report = {"date": time.strftime("%Y-%m-%d %H:%M"), "mode": "automated browser rehearsal, live LLM, ElevenAgents connected (fake mic), tab shared", "total_seconds": total, "under_six_minutes": total < 360, "behaviours": log}
    (OUT / "rehearsal_report.json").write_text(json.dumps(report, indent=1)); assert total < 360
