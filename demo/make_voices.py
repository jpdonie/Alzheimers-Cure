"""Generate the ElevenLabs voices for night-shift-apprentice.html.

Reads the dialogue from the page itself (the <script id="lines"> block), so text and audio never drift apart.
Writes one mp3 per line to ./audio/<line id>.mp3. The page plays these when present and falls back to the
browser's voice otherwise.

Usage:
  export ELEVENLABS_API_KEY=...            # never commit this
  export VOICE_PSY=<voice id>          # optional: the psychologist, speaks French
  export VOICE_CG=<voice id>           # optional: the care assistant, speaks English
  export VOICE_AP=<voice id>           # optional: the AI Apprentice, speaks English
  export VOICE_EXA=<voice id>          # optional: Expert A, speaks English
  python3 make_voices.py night-shift-apprentice.html
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"
MODEL = "eleven_multilingual_v2"  # one model for the French and English lines
VOICES = {
    # ElevenLabs premade voices; replace with your own picks from the Voice Library.
    "psy": os.environ.get("VOICE_PSY", "pNInz6obpgDQGcFmaJgB"),
    "cg": os.environ.get("VOICE_CG", "EXAVITQu4vr4xnSDxMaL"),
    "ap": os.environ.get("VOICE_AP", "21m00Tcm4TlvDq8ikWAM"),
    "exa": os.environ.get("VOICE_EXA", "ErXwobaYiN019PkySvjV"),
}


def load_lines(html_path):
    html = Path(html_path).read_text(encoding="utf-8")
    m = re.search(r'<script id="lines" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        sys.exit("No <script id=\"lines\"> block found in " + html_path)
    return json.loads(m.group(1))["lines"]


def tts(text, voice, key):
    body = json.dumps({
        "text": text.replace("…", "..."),
        "model_id": MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }).encode()
    req = urllib.request.Request(API.format(voice=voice), data=body, method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json",
                                          "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("Set ELEVENLABS_API_KEY first.")
    html_path = sys.argv[1] if len(sys.argv) > 1 else "night-shift-apprentice.html"
    out = Path(html_path).parent / "audio"
    out.mkdir(exist_ok=True)
    lines = load_lines(html_path)
    chars = sum(len(l[l["lang"]]) for l in lines)
    print(f"{len(lines)} lines, {chars} characters")
    for line in lines:
        target = out / f"{line['id']}.mp3"
        if target.exists():
            print("skip", target.name)
            continue
        target.write_bytes(tts(line[line["lang"]].replace("…", ","), VOICES[line["who"]], key))  # spoken in the line's own language
        print("wrote", target.name)


if __name__ == "__main__":
    main()
