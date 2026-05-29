from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_registry_payload(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["hash_registry_payload"]
