from __future__ import annotations

import json
from pathlib import Path

from modules.evaluation.simulators.llm_recommendation import run_simulation

INTENTS_PATH = Path(__file__).resolve().parent / "queries" / "shopping_intents.json"


def main() -> None:
    intents = json.loads(INTENTS_PATH.read_text(encoding="utf-8"))
    results = []
    for intent in intents:
        outcome = run_simulation(intent["id"], intent["utterance"], limit=3)
        results.append(outcome.__dict__)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
