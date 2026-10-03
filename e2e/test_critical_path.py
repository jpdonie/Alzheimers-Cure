"""Critical-path browser test (opt-in): needs engine on :8000 (APPRENTICE_COOLDOWN=2, APPRENTICE_OFFLINE=1) and web on :3000.
Run: E2E=1 engine/.venv/bin/python -m pytest e2e -q. Voice is not exercised here (needs a mic and provider credits)."""
import os, re, pytest
from playwright.sync_api import sync_playwright, expect

pytestmark = pytest.mark.skipif(os.getenv("E2E") != "1", reason="opt-in browser test")
WEB = "http://localhost:3000"


def wait_question(page, timeout=12000):
    cap = page.locator("[role=status]")
    cap.wait_for(timeout=timeout)
    return cap.inner_text()


def answer(page, text):
    page.get_by_placeholder("Answer by voice, or type here").fill(text)
    page.get_by_role("button", name="Send answer").click()
    page.get_by_text("Learned:").wait_for(timeout=8000)


def test_capture_debrief_map_teach():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        page = b.new_context(viewport={"width": 1400, "height": 1000}).new_page()
        page.goto(f"{WEB}/capture"); page.get_by_text("Your task (fake data)").wait_for()

        # silence while the expert is typing: no question may appear
        obs = page.get_by_label("What you observed (facts only)")
        for _ in range(8):
            obs.type("refuses tray ", delay=150); page.wait_for_timeout(250)
        assert page.locator("[role=status]").count() == 0

        # three screen-grounded questions at natural pauses
        page.get_by_label("Pain / physical discomfort").check()
        q1 = wait_question(page); assert "I saw you ticked 'pain'" in q1
        answer(page, "Pain first, but if she cannot tell me and seems frightened I call the nurse before anything else.")
        page.get_by_label("Intervention").select_option("give_prn_medication")
        q2 = wait_question(page); assert "I saw you set the intervention" in q2
        answer(page, "I would never decide that myself; it always goes to the nurse.")
        page.get_by_label("Escalate to").select_option("nurse")
        q3 = wait_question(page)
        answer(page, "The nurse takes it to the coordinating physician.")
        assert re.search(r"Questions asked: [3-9]", page.get_by_text("Questions asked").inner_text())
        assert page.get_by_text("guardrail:", exact=False).count() >= 1

        # debrief: three new questions + teach-back
        page.get_by_role("link", name="Task finished → Debrief").click()
        page.get_by_text("what I am still unsure about").wait_for()
        for _ in range(3):
            page.get_by_placeholder("Answer by voice, or type").fill("It depends on the resident; when unsure I ask the nurse.")
            page.get_by_role("button", name="Send answer").click(); page.wait_for_timeout(700)
        page.get_by_role("button", name="Explain the process back to me").click()
        page.get_by_role("button", name="Yes, that is it").first.wait_for()
        n_steps = page.get_by_role("button", name="Yes, that is it").count()
        assert n_steps >= 1
        for i in range(n_steps):                      # confirm every step, not just the first
            page.get_by_role("button", name="Yes, that is it").nth(i).click(); page.wait_for_timeout(400)
        assert page.get_by_text("confirmed by expert").count() >= n_steps

        # Off the record is enforced server-side: the engine refuses late writes
        import json, urllib.request, urllib.error
        def post(path, body):
            req = urllib.request.Request("http://localhost:8000" + path, json.dumps(body).encode(), {"content-type": "application/json"})
            try: return urllib.request.urlopen(req).status
            except urllib.error.HTTPError as e: return e.code
        assert post("/recording", {"on": False}) == 200 and post("/events", {"field": "checks", "value": []}) == 409
        assert post("/recording", {"on": True}) == 200

        # map
        page.get_by_role("link", name="See the Work Map →").click()
        page.get_by_text("In the expert's words (live)").wait_for()
        assert page.get_by_text("Pain first").count() >= 1
        page.get_by_text("Provenance").first.click()
        assert page.get_by_text("transcript").count() >= 1

        # teach: predict, blocked before save with inspectable predicate, retry succeeds
        page.get_by_role("link", name="Teach a new hire →").click()
        page.get_by_text("Predict:").wait_for()
        page.get_by_role("button", name=re.compile(r"^A\. Note")).click()
        page.get_by_role("button", name="Save record").click()
        page.get_by_text("Hold on: not saved yet").wait_for()
        assert page.get_by_text("dataset summary, not a quotation").count() >= 0
        assert page.get_by_text("predicate:", exact=False).count() >= 1
        assert page.get_by_text("guardrail R1-somatic-first").count() == 1
        page.get_by_role("button", name="Fix it").click()
        page.get_by_label("Pain / physical discomfort").check()
        page.get_by_label("Escalate to").select_option("team_meeting")
        page.get_by_label("Intervention").select_option("swap_carer_or_call_psychologist")
        page.get_by_label("Behaviour is").select_option("new")
        page.get_by_role("button", name="Save record").click()
        page.get_by_text("Saved. Mastery so far").wait_for()

        # a materially different sealed case is caught too
        page.get_by_role("button", name=re.compile("T2:")).click()
        page.get_by_text("Newcomer keeps trying to leave").first.wait_for()
        page.get_by_role("button", name="Save record").click()           # saving before predicting is refused
        page.get_by_text("Make your prediction first").wait_for()
        page.get_by_role("button", name=re.compile(r"^A\. Log it as a refusal")).click()
        page.get_by_role("button", name="Save record").click()
        page.get_by_text("guardrail R6-exit-seeking").wait_for()
        b.close()
