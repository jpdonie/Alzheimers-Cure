"""Load the de-identified dementia-care dataset into CareRule objects with provenance."""
import json
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "dementia_care_knowledge_deidentified.json"


@dataclass
class Provenance:
    session: str
    turn_ids: list[str]
    start: str
    end: str
    quote: str


@dataclass
class CareRule:
    rule_id: str
    domain: str
    context: str
    action: str
    rationale: str
    exceptions: list[str]
    guardrails: list[str]
    provenance: list[Provenance] = field(default_factory=list)
    confidence: float = 0.5
    priority: str = ""


def load_rules(path: Path = DATA) -> list[CareRule]:
    d = json.loads(Path(path).read_text())
    rules = []
    for s in d["sessions"]:
        turns = {t["turn_id"]: t for t in s["dialogue"]}
        for u in s["knowledge_units"]:
            ids = u.get("dialogue_turn_ids", [])
            quote = " ".join(turns[i]["text"] for i in ids[:2] if i in turns)[:400]
            rules.append(CareRule(
                rule_id=u["unit_id"],
                domain=u["domain"],
                context=u["subtopic"],
                action="; ".join(u.get("practice_rules", [])),
                rationale=u.get("clinical_rationale_why", ""),
                exceptions=[u["cautions_or_corrections"]] if u.get("cautions_or_corrections") else [],
                guardrails=[],  # filled by LLM slot-extraction / uncertainty loop
                provenance=[Provenance(s["session_id"], ids, u["start"], u["end"], quote)],
                priority=u.get("apprentice_priority", ""),
            ))
    return rules


if __name__ == "__main__":
    r = load_rules()
    print(len(r), "rules;", sum(1 for x in r if x.provenance), "with provenance")
