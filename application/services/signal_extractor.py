from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps


SKILL_ID = "signal-extractor-v1"
SKILL_NAME = "signal_extractor"
SKILL_VERSION = "2026-02-01"
SKILL_DESCRIPTION = (
    "Extract intent-level signals and missing concepts from query + product copy."
)

DEFAULT_SKILL_CONTENT = """# Signal Extraction Skill

You map user intent into **concept-level signals** (not raw tokens).
You must output JSON ONLY and follow the schema exactly.

## Goal
Given a user intent and product copy, identify:
- intent_signals: key concepts in the intent
- winner_signals: concepts the winning product emphasizes (if provided)
- missing_signals: concepts missing in our copy, expressed as short phrases to add

## Rules
- Do NOT output raw numbers or tokens unless they represent a concept (e.g., "price range").
- Normalize sizes and prices into concepts like "size availability" and "price range".
- Use short, actionable phrases (5–12 words).
- Prefer **phrases** over keywords.
- Limit each list to 5 items max.

## Output JSON schema
{
  "intent_signals": ["..."],
  "winner_signals": ["..."],
  "missing_signals": ["..."]
}
"""


@dataclass(frozen=True)
class SignalExtraction:
    intent_signals: List[str]
    winner_signals: List[str]
    missing_signals: List[str]


class SignalExtractor:
    def __init__(self, deps: AppDeps) -> None:
        self._deps = deps

    def extract(
        self,
        *,
        goal: str,
        product: Dict[str, Any],
        winner: Optional[Dict[str, Any]] = None,
    ) -> Optional[SignalExtraction]:
        try:
            skill = self._ensure_skill()
            payload = {
                "goal": goal,
                "product": {
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "description": product.get("description"),
                },
                "winner": {
                    "id": (winner or {}).get("id"),
                    "name": (winner or {}).get("name"),
                    "description": (winner or {}).get("description"),
                }
                if winner
                else None,
            }
            prompt = (
                f"{skill}\n\nINPUT JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
                "Return JSON only."
            )
            raw = self._deps.generate(prompt)
            data = _extract_json(raw)
            if not data:
                return None
            return SignalExtraction(
                intent_signals=_ensure_list(data.get("intent_signals")),
                winner_signals=_ensure_list(data.get("winner_signals")),
                missing_signals=_ensure_list(data.get("missing_signals")),
            )
        except Exception:
            return None

    def _ensure_skill(self) -> str:
        existing = self._deps.skills.get_skill(name=SKILL_NAME)
        if existing:
            return str(existing.get("content") or "")
        self._deps.skills.upsert_skill(
            skill_id=SKILL_ID,
            name=SKILL_NAME,
            description=SKILL_DESCRIPTION,
            version=SKILL_VERSION,
            content=DEFAULT_SKILL_CONTENT,
            enabled=True,
            metadata={"purpose": "signal_extraction"},
        )
        return DEFAULT_SKILL_CONTENT


def _extract_json(raw: str) -> Dict[str, Any] | None:
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # Fallback: first JSON object in text
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _ensure_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


__all__ = ["SignalExtractor", "SignalExtraction"]
