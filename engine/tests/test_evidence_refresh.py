import json
from engine import evidence_refresh as E
from engine.session import load_rules

HTML = """<html><head><style>x{}</style><script>var a=1</script></head><body><nav>Menu Home</nav>
<h1>Aggression and anger</h1><p>Aggressive behavior may be triggered by pain, hunger, hearing problems or an unfamiliar environment. Check for physical causes such as pain or infection first.
Stay calm and speak slowly. Avoid arguing with the person during an episode.</p><footer>copyright</footer></body></html>"""


def test_extract_text_drops_navigation_and_scripts():
    t = E.extract_text(HTML)
    assert "Aggressive behavior may be triggered by pain" in t and "Menu" not in t and "var a" not in t and "copyright" not in t


def test_public_context_comes_only_from_the_cache_and_names_its_source(tmp_path):
    cache = tmp_path / "c.json"
    cache.write_text(json.dumps({"fetched_at": "2026-10-04", "provider": "BrightData Web Unlocker",
                                 "pages": [{"url": "https://example.org/a", "ok": True, "passages": E.passages(E.extract_text(HTML))}, {"url": "https://example.org/b", "ok": False, "passages": []}]}))
    r1 = next(r for r in load_rules() if r["id"] == "R1-somatic-first")
    out = E.public_context(r1, cache=cache)
    assert out and out[0]["url"] == "https://example.org/a" and out[0]["fetched_at"] == "2026-10-04"
    assert E.public_context(r1, cache=tmp_path / "missing.json") == []          # no cache, no content: nothing is invented


def test_refresh_requires_zone_configuration(monkeypatch):
    import pytest
    monkeypatch.delenv("BRIGHTDATA_UNLOCKER_ZONE", raising=False)
    with pytest.raises(SystemExit):
        E.refresh()
