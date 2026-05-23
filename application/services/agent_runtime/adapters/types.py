from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


class AdapterExecutionError(ValueError):
    pass


@dataclass(frozen=True)
class AdapterRequest:
    adapter_id: str
    channel_type: str
    capability_name: str
    client_id: str
    user_id: str | None
    inputs: Mapping[str, Any]


@dataclass(frozen=True)
class AdapterReceipt:
    receipt_id: str
    adapter_id: str
    channel_type: str
    capability_name: str
    permission_scope: str
    effect_class: str
    status: str
    subject: Mapping[str, Any] = field(default_factory=dict)
    evidence: Mapping[str, Any] = field(default_factory=dict)
    risk: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def stable_receipt_id(
    *,
    adapter_id: str,
    capability_name: str,
    client_id: str,
    subject: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> str:
    payload = {
        "adapter_id": adapter_id,
        "capability_name": capability_name,
        "client_id": client_id,
        "subject": dict(subject),
        "evidence": dict(evidence),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return f"receipt_{hashlib.sha256(encoded).hexdigest()[:24]}"
