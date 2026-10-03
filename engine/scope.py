"""Fail-closed clinical boundary: anything about medication, injury, emergency or acute deterioration goes to a human.
Deliberately a transparent lexicon, not a model: it must be explainable and must never depend on a provider."""
import re

ESCALATE = re.compile(r"\b(medicat\w*|dose|dosage|tablets?|pills?|sedat\w*|prn|prescri\w*|paracetamol|insulin|antibiotic\w*|fell|fall(?:en)?|head injury|hit (?:her|his|their) head|"
                      r"chest pain|breath\w*|choking|chok\w*|unresponsive|won'?t wake|seizure|bleeding|fever|stroke|emergency|overdose|stop (?:her|his|their) \w+ (?:tablets?|medication))\b", re.I)


def classify(text: str) -> dict:
    m = ESCALATE.search(text)
    return {"escalate": bool(m), "term": m.group(0) if m else "", "reason": f"mentions '{m.group(0)}': a qualified clinician must decide" if m else ""}
