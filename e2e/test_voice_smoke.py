"""Opt-in live smoke test (uses ElevenLabs credits, a few seconds of speech): VOICE=1.
Chrome's fake microphone stands in for a person; asserts the agent connects and voices the engine's question."""
import os, pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(os.getenv("VOICE") != "1", reason="opt-in; spends provider credits")


def test_agent_speaks_the_engine_question():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
        ctx = b.new_context(permissions=["microphone"], viewport={"width": 1400, "height": 1000}); page = ctx.new_page()
        page.goto("http://localhost:3000/capture"); page.get_by_text("Your task (fake data)").wait_for()
        page.get_by_role("button", name="Start voice").click()
        page.get_by_role("button", name="Voice connected").wait_for(timeout=20000)
        page.get_by_label("Pain / physical discomfort").check()
        page.locator("[role=status]").wait_for(timeout=15000)
        page.get_by_text("Asking", exact=True).wait_for(timeout=20000)   # agent is speaking the question
        assert page.get_by_text("Voice unavailable").count() == 0
        b.close()
