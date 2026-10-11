"""Exact action selection shared by review and recovery proposals."""

import re
from typing import Any


def resolve_action_target(
    question: str, actions: list[dict[str, Any]], *, source_status: str | frozenset[str] = "proposed"
) -> str:
    pending = [a for a in actions if a["status"] in ({source_status} if isinstance(source_status, str) else source_status)]
    if re.search(r"\bactions\b", question, re.IGNORECASE):
        raise ValueError("Select an exact action")
    mentioned = [
        a
        for a in actions
        if re.search(rf"(?<![\w-]){re.escape(a['id'])}(?![\w-])", question)
    ]
    references = list(
        re.finditer(r"\baction\s+(?:number\s+|#)?([\w-]+)", question, re.IGNORECASE)
    )
    targets = [
        match.group(1)
        for match in references
        if match.group(1).lower() not in {"please", "now"}
    ]
    # Collect shorthand list tails as well as repeated explicit action references.
    for reference in references:
        tail = question[reference.end() :]
        while match := re.match(
            r"\s*(?:,|&|/|\band\b|\bor\b)\s*(?:action\s+)?(?:number\s+|#)?([\w-]+)",
            tail,
            re.IGNORECASE,
        ):
            targets.append(match.group(1))
            tail = tail[match.end() :]
    targets.extend(
        re.findall(
            r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", question, re.IGNORECASE
        )
    )
    for target in targets:
        matches = [
            a
            for a in actions
            if a["id"] == target
            or target.isdigit()
            and a.get("sequence") == int(target)
        ]
        if len(matches) != 1:
            raise ValueError("Select an exact action")
        mentioned.extend(matches)
    ids = {a["id"] for a in mentioned}
    if len(ids) == 1:
        return ids.pop()
    if len(ids) > 1:
        raise ValueError("Select an exact action")
    if len(pending) == 1:
        return pending[0]["id"]
    raise ValueError("Select an exact action")
