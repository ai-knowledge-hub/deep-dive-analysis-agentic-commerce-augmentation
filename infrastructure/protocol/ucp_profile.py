from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from domain.protocol.types import ProtocolReadinessIssue
from infrastructure.db.catalog.platform_profiles import (
    DEFAULT_PROFILE_ID,
    ensure_platform_profile,
    get_platform_profile,
)

try:
    from jsonschema import Draft202012Validator, RefResolver
except Exception:  # pragma: no cover - optional dependency for local validation
    Draft202012Validator = None
    RefResolver = None

PINNED_UCP_VERSION = "2026-01-11"
REQUIRED_CAPABILITIES: Set[Tuple[str, str]] = {
    ("dev.ucp.shopping.checkout", PINNED_UCP_VERSION),
    ("dev.ucp.shopping.order", PINNED_UCP_VERSION),
}

SCHEMA_DIR = Path("data/protocol_schemas/ucp") / PINNED_UCP_VERSION
PROFILE_SCHEMA_ID = "https://ucp.dev/schemas/discovery/profile.json"
PLATFORM_PROFILE_PATH = Path("data/platform_profiles/ucp_platform_2026-01-11.json")


@dataclass(frozen=True)
class UcpProfileReport:
    ok: bool
    issues: List[ProtocolReadinessIssue]
    capabilities: Set[Tuple[str, str]]
    rest_endpoint: Optional[str]


def load_schema_store() -> Dict[str, Dict[str, Any]]:
    store: Dict[str, Dict[str, Any]] = {}
    if not SCHEMA_DIR.exists():
        return store
    for path in SCHEMA_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        schema_id = data.get("$id")
        if isinstance(schema_id, str):
            store[schema_id] = data
            if "/schemas/schemas/" in schema_id:
                store[schema_id.replace("/schemas/schemas/", "/schemas/")] = data
            else:
                store[schema_id.replace("/schemas/", "/schemas/schemas/")] = data
    return store


def validate_ucp_profile(profile: Dict[str, Any]) -> UcpProfileReport:
    issues: List[ProtocolReadinessIssue] = []
    relax_oneof = os.getenv("UCP_RELAX_ONEOF", "false").lower() in {"1", "true", "yes"}
    store = load_schema_store()
    platform_caps = load_platform_capabilities()
    if not platform_caps:
        issues.append(
            ProtocolReadinessIssue(
                field="platform_profile",
                severity="warning",
                message="Platform profile missing or invalid; using default required capabilities.",
                fix="Ensure data/platform_profiles/ucp_platform_2026-01-11.json exists and is pinned.",
            )
        )

    if Draft202012Validator is None or RefResolver is None:
        issues.append(
            ProtocolReadinessIssue(
                field="ucp_profile",
                severity="warning",
                message="jsonschema not installed; skipping schema validation.",
                fix="Install jsonschema>=4.18 to enable UCP profile validation.",
            )
        )
    elif not store:
        issues.append(
            ProtocolReadinessIssue(
                field="ucp_profile",
                severity="warning",
                message="UCP schema store missing; skipping schema validation.",
                fix="Add schemas under data/protocol_schemas/ucp/2026-01-11.",
            )
        )
    else:
        schema = store.get(PROFILE_SCHEMA_ID)
        if schema:
            resolver = RefResolver.from_schema(schema, store=store)
            validator = Draft202012Validator(schema, resolver=resolver)
            for err in validator.iter_errors(profile):
                path = ".".join(str(p) for p in err.path) or "$"
                if (
                    relax_oneof
                    and err.validator == "oneOf"
                    and "is valid under each of" in err.message
                ):
                    issues.append(
                        ProtocolReadinessIssue(
                            field=path,
                            severity="warning",
                            message="UCP profile matches multiple schema variants; accepting in demo mode.",
                            fix="Adjust profile to match only business schema in production.",
                        )
                    )
                    continue
                issues.append(
                    ProtocolReadinessIssue(
                        field=path,
                        severity="error",
                        message=err.message,
                        fix="Fix UCP business profile schema violations.",
                    )
                )
        else:
            issues.append(
                ProtocolReadinessIssue(
                    field="ucp_profile",
                    severity="warning",
                    message="UCP profile schema not found in store.",
                    fix="Ensure discovery/profile_schema.json is present.",
                )
            )

    ucp = profile.get("ucp") if isinstance(profile, dict) else None
    capabilities = _extract_capabilities(ucp) if isinstance(ucp, dict) else set()
    rest_endpoint = _extract_rest_endpoint(ucp) if isinstance(ucp, dict) else None

    if isinstance(ucp, dict):
        version = ucp.get("version")
        if version != PINNED_UCP_VERSION:
            issues.append(
                ProtocolReadinessIssue(
                    field="ucp.version",
                    severity="error",
                    message=f"UCP version must be {PINNED_UCP_VERSION}; got {version!r}.",
                    fix="Pin UCP version to 2026-01-11.",
                )
            )
    else:
        issues.append(
            ProtocolReadinessIssue(
                field="ucp",
                severity="error",
                message="Missing ucp object in business profile.",
                fix="Provide ucp metadata with version, services, capabilities.",
            )
        )

    if not rest_endpoint:
        issues.append(
            ProtocolReadinessIssue(
                field="ucp.services",
                severity="error",
                message="Missing REST endpoint in ucp.services; cannot resolve capability endpoints.",
                fix="Add a REST service entry with an endpoint URL.",
            )
        )

    required_caps = platform_caps or REQUIRED_CAPABILITIES
    missing_required = required_caps.difference(capabilities)
    for name, version in sorted(missing_required):
        issues.append(
            ProtocolReadinessIssue(
                field="ucp.capabilities",
                severity="error",
                message=f"Missing required capability {name}@{version}.",
                fix="Add required capability entries to ucp.capabilities.",
            )
        )
    missing_on_platform = capabilities.difference(required_caps)
    for name, version in sorted(missing_on_platform):
        issues.append(
            ProtocolReadinessIssue(
                field="ucp.capabilities",
                severity="warning",
                message=f"Capability {name}@{version} not supported by platform profile.",
                fix="Add capability to platform profile or remove from business profile.",
            )
        )

    readiness_score = _compute_readiness_score(issues, rest_endpoint, missing_required)
    issues.append(
        ProtocolReadinessIssue(
            field="ucp_readiness_score",
            severity="info",
            message=f"UCP readiness score: {readiness_score}/100.",
        )
    )

    ok = not any(issue.severity == "error" for issue in issues)
    return UcpProfileReport(
        ok=ok, issues=issues, capabilities=capabilities, rest_endpoint=rest_endpoint
    )


def _extract_capabilities(ucp: Dict[str, Any]) -> Set[Tuple[str, str]]:
    caps: Set[Tuple[str, str]] = set()
    raw = ucp.get("capabilities")
    if isinstance(raw, dict):
        for name, entries in raw.items():
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        version = entry.get("version") or PINNED_UCP_VERSION
                        caps.add((str(name), str(version)))
    elif isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict):
                name = entry.get("name")
                version = entry.get("version") or PINNED_UCP_VERSION
                if name:
                    caps.add((str(name), str(version)))
    return caps


def _extract_rest_endpoint(ucp: Dict[str, Any]) -> Optional[str]:
    services = ucp.get("services")
    if isinstance(services, dict):
        if isinstance(services.get("rest"), dict):
            endpoint = services["rest"].get("endpoint")
            if isinstance(endpoint, str):
                return endpoint
        for entries in services.values():
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    endpoint = entry.get("endpoint")
                    if isinstance(endpoint, str):
                        return endpoint
                    config = entry.get("config")
                    if isinstance(config, dict) and isinstance(
                        config.get("endpoint"), str
                    ):
                        return config["endpoint"]
    return None


def _compute_readiness_score(
    issues: Iterable[ProtocolReadinessIssue],
    rest_endpoint: Optional[str],
    missing_required: Set[Tuple[str, str]],
) -> int:
    score = 100
    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    if error_count:
        score -= min(50, 10 * error_count)
    if warning_count:
        score -= min(20, 5 * warning_count)
    if not rest_endpoint:
        score -= 15
    if missing_required:
        score -= min(30, 10 * len(missing_required))
    return max(0, min(100, score))


def load_platform_capabilities() -> Set[Tuple[str, str]]:
    stored = get_platform_profile(profile_id=DEFAULT_PROFILE_ID)
    if not stored:
        data = _load_platform_profile_from_file()
        if data:
            stored = ensure_platform_profile(
                profile_id=DEFAULT_PROFILE_ID,
                name=data.get("name") or "UCP Platform Profile",
                version=data.get("version") or PINNED_UCP_VERSION,
                profile=data,
            )
    data = stored.get("profile") if stored else None
    if not isinstance(data, dict):
        data = _load_platform_profile_from_file()
    if not isinstance(data, dict) or data.get("version") != PINNED_UCP_VERSION:
        return set()
    caps: Set[Tuple[str, str]] = set()
    for entry in data.get("capabilities", []) or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        version = entry.get("version")
        if isinstance(name, str) and isinstance(version, str):
            caps.add((name, version))
    return caps


def _load_platform_profile_from_file() -> Optional[Dict[str, Any]]:
    if not PLATFORM_PROFILE_PATH.exists():
        return None
    try:
        return json.loads(PLATFORM_PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


__all__ = [
    "PINNED_UCP_VERSION",
    "REQUIRED_CAPABILITIES",
    "UcpProfileReport",
    "load_schema_store",
    "load_platform_capabilities",
    "validate_ucp_profile",
]
