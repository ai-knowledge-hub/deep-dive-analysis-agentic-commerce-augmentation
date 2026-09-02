from __future__ import annotations

from typing import Any, Dict, Mapping


def canonicalize_inputs(
    *,
    defaults: Mapping[str, Any],
    canonicalizers: Mapping[str, str],
    inputs: Mapping[str, Any],
) -> Dict[str, Any]:
    canonical: Dict[str, Any] = dict(defaults)
    canonical.update({str(key): value for key, value in dict(inputs or {}).items()})
    for key, rule in canonicalizers.items():
        value = canonical.get(key)
        if value is None or type(value) is not str:
            continue
        stripped = value.strip()
        if rule == "strip":
            canonical[key] = stripped
        elif rule == "strip_lower":
            canonical[key] = stripped.lower()
        elif rule == "strip_or_none":
            canonical[key] = stripped or None
        elif rule == "strip_or_default":
            canonical[key] = stripped or defaults.get(key)
        elif rule == "strip_lower_or_default":
            canonical[key] = stripped.lower() or defaults.get(key)
        else:
            raise ValueError(f"Unsupported input canonicalizer {rule!r} for {key!r}")
    return canonical


def default_input_properties(defaults: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: _property_for_value(value) for key, value in defaults.items()}


def object_schema(
    *, required: tuple[str, ...], properties: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": True,
    }


def _property_for_value(value: Any) -> Dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "boolean", "default": value}
    if isinstance(value, int):
        return {"type": "integer", "default": value}
    if isinstance(value, float):
        return {"type": "number", "default": value}
    return {"type": "string", "default": value}


__all__ = ["canonicalize_inputs", "default_input_properties", "object_schema"]
