"""Check that every quoted line in night-shift-apprentice.html is word for word in the transcripts.

Lines with a source id (S13-T0335 etc.) must match the dataset: the original-language text against `text`,
the English under a French turn against `english_translation`. "…" marks a cut; each piece is checked on its own.
AI Apprentice lines (no source id) are ours and are listed, not checked.

Usage: python3 verify_lines.py night-shift-apprentice.html path/to/dementia_care_knowledge_deidentified.json
"""
import json, re, sys
from pathlib import Path

norm = lambda s: re.sub(r"\s+", " ", s).strip(" .,;:!?—-").lower()

def main(html_path, data_path):
    html = Path(html_path).read_text(encoding="utf-8")
    lines = json.loads(re.search(r'<script id="lines" type="application/json">(.*?)</script>', html, re.S).group(1))["lines"]
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    turns = {t["turn_id"]: t for s in data["sessions"] for t in s["dialogue"]}
    bad = ours = 0
    for l in lines:
        if not re.match(r"S\d\d-T\d+$", l["id"]):
            ours += 1
            continue
        t = turns[l["id"]]
        checks = [(l[l["lang"]], t["text"], "original")]
        if l["lang"] == "fr":
            checks.append((l["en"], t.get("english_translation") or "", "translation"))
        for shown, source, what in checks:
            for piece in shown.split("…"):
                if norm(piece) and norm(piece) not in norm(source):
                    bad += 1
                    print(f"MISMATCH {l['id']} {what}: {piece.strip()[:80]}")
        if l.get("t") and l["t"] != t["start"]:
            bad += 1
            print(f"TIME {l['id']}: shown {l['t']}, source {t['start']}")
    print(f"{len(lines) - ours} quoted lines checked, {bad} problems. {ours} AI Apprentice lines (ours, not checked).")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main(*sys.argv[1:3])
