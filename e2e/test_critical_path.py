"""Critical-path browser test (opt-in): needs engine on :8000 (APPRENTICE_COOLDOWN=2, APPRENTICE_OFFLINE=1) and web on :3000.
Run: E2E=1 engine/.venv/bin/python -m pytest e2e -q. Voice is not exercised here (needs a mic and provider credits)."""
import os, re, pytest
from playwright.sync_api import sync_playwright, expect

pytestmark = pytest.mark.skipif(os.getenv("E2E") != "1", reason="opt-in browser test")
WEB = "http://localhost:3000"


def wait_question(page, timeout=30000):
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

        # the micro case record is on screen, and its answer is not
        assert page.get_by_text("Day 6, 15:50").count() == 1 and page.get_by_text("sundowning", exact=False).count() >= 1
        assert page.get_by_text("looking for the toilet", exact=False).count() == 0

        # silence while the expert is typing: no question may appear
        obs = page.get_by_label("What you observed (facts only)")
        for _ in range(8):
            obs.type("pacing the east corridor, trying doors ", delay=150); page.wait_for_timeout(250)
        assert page.locator("[role=status]").count() == 0
        page.get_by_label("Incident type").select_option("wandering")

        # three screen-grounded questions at natural pauses, about what the expert just did
        page.get_by_role("checkbox", name="Toileting").check()
        q1 = wait_question(page); assert "I saw you ticked 'toileting'" in q1
        answer(page, "Toileting first: the episodes start after the drinks round and he was calm after the bathroom. If he cannot tell me I ask the nurse.")
        page.get_by_role("checkbox", name="Signage, routine, schedule changes").check()
        q2 = wait_question(page); assert "I saw you ticked 'signage routine'" in q2
        answer(page, "The plaques were taken down the same week it began, so I check what changed in the building and the schedule.")
        page.get_by_label("Intervention").select_option("prompted_toileting")
        q3 = wait_question(page); assert "I saw you set the intervention to 'prompt toileting'" in q3
        answer(page, "Never medication first. If toileting does not settle it, it goes to the nurse and the team meeting.")
        assert re.search(r"Questions asked: [3-9]", page.get_by_text("Questions asked").inner_text())
        assert page.get_by_text("guardrail:", exact=False).count() >= 1

        # debrief: three new questions + teach-back
        page.get_by_role("link", name="Task finished → Debrief").click()
        page.get_by_text("what I am still unsure about").wait_for()
        for i in range(3):
            page.get_by_placeholder("Answer by voice, or type").fill("It depends on the resident; when unsure I ask the nurse.")
            page.get_by_role("button", name="Send answer").click()
            expect(page.locator("ul.mt-2.text-sm > li")).to_have_count(i + 1, timeout=10000)
        expect(page.get_by_role("button", name="Explain the process back to me")).to_be_enabled(timeout=10000)
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
        assert page.get_by_text("Toileting first").count() >= 1
        page.get_by_text("Provenance").first.click()
        assert page.get_by_text("transcript").count() >= 1

        # graph: the live moment is a node connected to its rule, and the learner's re-derivations are shown
        page.goto(f"{WEB}/graph"); page.get_by_text("nodes,", exact=False).wait_for(timeout=20000)
        assert page.get_by_text("independently re-derived", exact=False).count() == 1
        page.get_by_placeholder("Search: pain, nurse, KU-S13-20…").fill("somatic"); page.wait_for_timeout(500)
        page.goto(f"{WEB}/teach"); page.get_by_text("Step 1 · Predict before editing").wait_for()
        page.get_by_role("button", name=re.compile("T1:")).click()
        # teach: predict, blocked before save with inspectable predicate, retry succeeds
        page.get_by_role("button", name=re.compile(r"^A\. Note")).click()
        page.get_by_role("button", name="Save record").click()
        page.get_by_text("Hold on: not saved yet").wait_for()
        assert page.get_by_text("dataset summary, not a quotation").count() == 0     # R1/R3 have verbatim spans only
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
        page.get_by_role("button", name="Fix it").click()

        # T3: the medication rule is backed only by dataset summaries, which must never be shown as quotations
        page.get_by_role("button", name=re.compile("T3:")).click()
        page.get_by_text("Restless in the evening").first.wait_for()
        page.get_by_role("button", name=re.compile(r"^A\. Give the PRN")).click()
        page.get_by_label("Intervention").select_option("give_prn_medication")
        page.get_by_role("button", name="Save record").click()
        page.get_by_text("guardrail R4-treatment-routing").wait_for()
        assert page.get_by_text("dataset summary, not a quotation").count() >= 1
        page.get_by_role("button", name="Fix it").click()

        # T4: the wandering transfer case. "It is sundowning, ask for an antipsychotic" is stopped for the right reasons,
        # and evidence taken from the startup team's composite case is labelled as such, never as an interview quote
        page.get_by_role("button", name=re.compile("T4:")).click()
        page.get_by_text("Afternoon pacing at the corridor doors").first.wait_for()
        page.get_by_role("button", name=re.compile(r"^A\. Record it as sundowning")).click()
        page.get_by_label("Intervention").select_option("request_antipsychotic")
        page.get_by_role("button", name="Save record").click()
        page.get_by_text("guardrail R7-wandering-basic-needs").wait_for()
        page.get_by_text("guardrail R4-treatment-routing").wait_for()
        assert page.get_by_text("composite case, invented details").count() >= 1
        b.close()
