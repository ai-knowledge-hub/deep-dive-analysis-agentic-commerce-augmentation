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
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except Exception:  # pragma: no cover - optional dependency for local validation
    Draft202012Validator = None
    Registry = None
    Resource = None

PINNED_UCP_VERSION = "2026-01-11"
CURRENT_UCP_VERSION = "2026-04-08"
SUPPORTED_UCP_VERSIONS = {PINNED_UCP_VERSION, CURRENT_UCP_VERSION}
REQUIRED_CAPABILITY_NAMES: Set[str] = {"dev.ucp.shopping.checkout"}
RECOMMENDED_CAPABILITY_NAMES: Set[str] = {
    "dev.ucp.shopping.cart",
    "dev.ucp.shopping.order",
}
REQUIRED_CAPABILITIES: Set[Tuple[str, str]] = {
    ("dev.ucp.shopping.checkout", PINNED_UCP_VERSION),
}

SCHEMA_DIR = Path("data/protocol_schemas/ucp") / PINNED_UCP_VERSION
PROFILE_SCHEMA_ID = "https://ucp.dev/schemas/discovery/profile.json"
PLATFORM_PROFILE_PATH = Path("data/platform_profiles/ucp_platform_2026-01-11.json")
CURRENT_PLATFORM_PROFILE_PATH = Path("data/platform_profiles/ucp_platform_2026-04-08.json")


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
    profile_version = _extract_profile_version(profile)
    store = load_schema_store() if profile_version == PINNED_UCP_VERSION else {}
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

    if profile_version != PINNED_UCP_VERSION:
        issues.append(
            ProtocolReadinessIssue(
                field="ucp_profile",
                severity="info",
                message=(
                    "Using structural UCP validation for current profile version "
                    f"{profile_version or 'unknown'}; bundled JSON Schema validation "
                    f"remains pinned to {PINNED_UCP_VERSION}."
                ),
                fix=(
                    f"Add bundled {profile_version} schemas when strict offline "
                    "validation is required."
                ),
            )
        )
    elif Draft202012Validator is None or Registry is None or Resource is None:
        issues.append(
            ProtocolReadinessIssue(
                field="ucp_profile",
                severity="warning",
                message="jsonschema/referencing not installed; skipping schema validation.",
                fix="Install jsonschema>=4.18 and referencing to enable UCP profile validation.",
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
            registry = Registry()
            for schema_id, schema_doc in store.items():
                try:
                    registry = registry.with_resource(
                        schema_id, Resource.from_contents(schema_doc)
                    )
                except Exception:
                    continue
            validator = Draft202012Validator(schema, registry=registry)
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
        version = str(ucp.get("version") or "")
        if version not in SUPPORTED_UCP_VERSIONS:
            issues.append(
                ProtocolReadinessIssue(
                    field="ucp.version",
                    severity="error",
                    message=(
                        "Unsupported UCP version "
                        f"{version!r}; supported versions are "
                        f"{', '.join(sorted(SUPPORTED_UCP_VERSIONS))}."
                    ),
                    fix=(
                        f"Publish a {CURRENT_UCP_VERSION} profile or include a "
                        "supported_versions entry for a compatible profile."
                    ),
                )
            )
        supported_versions = ucp.get("supported_versions")
        if supported_versions is not None and not isinstance(supported_versions, dict):
            issues.append(
                ProtocolReadinessIssue(
                    field="ucp.supported_versions",
                    severity="error",
                    message="supported_versions must be an object mapping version to profile URI.",
                    fix="Use {\"2026-01-11\": \"https://.../.well-known/ucp/2026-01-11\"}.",
                )
            )
        issues.extend(_validate_services(ucp))
        issues.extend(_validate_payment_handlers(ucp))
        issues.extend(_validate_signing_keys(profile))
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

    capability_names = {name for name, _version in capabilities}
    missing_required_names = REQUIRED_CAPABILITY_NAMES.difference(capability_names)
    for name in sorted(missing_required_names):
        issues.append(
            ProtocolReadinessIssue(
                field="ucp.capabilities",
                severity="error",
                message=f"Missing required capability {name}.",
                fix="Add required capability entries to ucp.capabilities.",
            )
        )
    missing_recommended_names = RECOMMENDED_CAPABILITY_NAMES.difference(capability_names)
    for name in sorted(missing_recommended_names):
        issues.append(
            ProtocolReadinessIssue(
                field="ucp.capabilities",
                severity="warning",
                message=f"Recommended capability {name} is not advertised.",
                fix="Advertise cart/order capabilities when the business supports them.",
            )
        )
    platform_cap_names = {name for name, _version in platform_caps}
    missing_on_platform = (
        capability_names.difference(platform_cap_names) if platform_cap_names else set()
    )
    for name in sorted(missing_on_platform):
        issues.append(
            ProtocolReadinessIssue(
                field="ucp.capabilities",
                severity="warning",
                message=f"Capability {name} not supported by platform profile.",
                fix="Add capability to platform profile or remove from business profile.",
            )
        )

    readiness_score = _compute_readiness_score(
        issues,
        rest_endpoint,
        {(name, profile_version or "") for name in missing_required_names},
    )
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


def _extract_profile_version(profile: Dict[str, Any]) -> Optional[str]:
    ucp = profile.get("ucp") if isinstance(profile, dict) else None
    version = ucp.get("version") if isinstance(ucp, dict) else None
    return str(version) if isinstance(version, str) and version.strip() else None


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


def _validate_services(ucp: Dict[str, Any]) -> List[ProtocolReadinessIssue]:
    issues: List[ProtocolReadinessIssue] = []
    services = ucp.get("services")
    if not isinstance(services, dict):
        return [
            ProtocolReadinessIssue(
                field="ucp.services",
                severity="error",
                message="UCP services must be an object keyed by service name.",
                fix="Publish services such as dev.ucp.shopping with transport entries.",
            )
        ]
    seen_rest = False
    for service_name, entries in services.items():
        if not isinstance(entries, list):
            issues.append(
                ProtocolReadinessIssue(
                    field=f"ucp.services.{service_name}",
                    severity="error",
                    message="Service entries must be arrays of transport bindings.",
                    fix="Use an array of REST/MCP/A2A/embedded service declarations.",
                )
            )
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            path = f"ucp.services.{service_name}[{index}]"
            transport = entry.get("transport")
            endpoint = entry.get("endpoint")
            schema = entry.get("schema")
            if transport not in {"rest", "mcp", "a2a", "embedded"}:
                issues.append(
                    ProtocolReadinessIssue(
                        field=f"{path}.transport",
                        severity="error",
                        message="Service transport must be one of rest, mcp, a2a, embedded.",
                        fix="Set transport to a supported UCP transport.",
                    )
                )
            if transport in {"rest", "mcp", "embedded"} and not schema:
                issues.append(
                    ProtocolReadinessIssue(
                        field=f"{path}.schema",
                        severity="error",
                        message=f"{transport} service binding must include schema URL.",
                        fix="Reference the OpenAPI/OpenRPC schema for this transport.",
                    )
                )
            if transport in {"rest", "mcp", "a2a"}:
                if not isinstance(endpoint, str) or not endpoint:
                    issues.append(
                        ProtocolReadinessIssue(
                            field=f"{path}.endpoint",
                            severity="error",
                            message=f"{transport} service binding must include endpoint URL.",
                            fix="Publish an HTTPS endpoint for this transport.",
                        )
                    )
                elif not endpoint.startswith("https://"):
                    issues.append(
                        ProtocolReadinessIssue(
                            field=f"{path}.endpoint",
                            severity="error",
                            message="UCP endpoint must use HTTPS.",
                            fix="Serve UCP transport endpoints over HTTPS.",
                        )
                    )
            if transport == "rest":
                seen_rest = True
    if not seen_rest:
        issues.append(
            ProtocolReadinessIssue(
                field="ucp.services",
                severity="warning",
                message="No REST service binding advertised.",
                fix="Advertise REST if checkout/cart/order APIs are available over HTTP.",
            )
        )
    return issues


def _validate_payment_handlers(ucp: Dict[str, Any]) -> List[ProtocolReadinessIssue]:
    raw = ucp.get("payment_handlers")
    if raw is None:
        return [
            ProtocolReadinessIssue(
                field="ucp.payment_handlers",
                severity="warning",
                message="No payment_handlers registry advertised.",
                fix="Declare supported payment handlers when checkout is supported.",
            )
        ]
    if not isinstance(raw, dict):
        return [
            ProtocolReadinessIssue(
                field="ucp.payment_handlers",
                severity="error",
                message="payment_handlers must be an object keyed by handler name.",
                fix="Publish payment handler entries as arrays keyed by reverse-domain name.",
            )
        ]
    issues: List[ProtocolReadinessIssue] = []
    for handler_name, entries in raw.items():
        if not isinstance(entries, list):
            issues.append(
                ProtocolReadinessIssue(
                    field=f"ucp.payment_handlers.{handler_name}",
                    severity="error",
                    message="Payment handler entries must be arrays.",
                    fix="Use an array of payment handler declarations.",
                )
            )
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            if not entry.get("id"):
                issues.append(
                    ProtocolReadinessIssue(
                        field=f"ucp.payment_handlers.{handler_name}[{index}].id",
                        severity="error",
                        message="Payment handler entries require an id.",
                        fix="Set a stable id to disambiguate handler configurations.",
                    )
                )
            instruments = entry.get("available_instruments")
            if instruments is not None and not isinstance(instruments, list):
                issues.append(
                    ProtocolReadinessIssue(
                        field=(
                            f"ucp.payment_handlers.{handler_name}[{index}]"
                            ".available_instruments"
                        ),
                        severity="error",
                        message="available_instruments must be an array when present.",
                        fix="List instrument descriptors with type and optional constraints.",
                    )
                )
    return issues


def _validate_signing_keys(profile: Dict[str, Any]) -> List[ProtocolReadinessIssue]:
    raw = profile.get("signing_keys")
    if raw is None:
        return [
            ProtocolReadinessIssue(
                field="signing_keys",
                severity="warning",
                message="No signing_keys advertised for UCP profile identity.",
                fix="Publish JWK signing keys when message signatures or webhooks are used.",
            )
        ]
    if not isinstance(raw, list):
        return [
            ProtocolReadinessIssue(
                field="signing_keys",
                severity="error",
                message="signing_keys must be an array of JWK public keys.",
                fix="Publish signing_keys as a JWK array with kid, kty, use, and alg.",
            )
        ]
    issues: List[ProtocolReadinessIssue] = []
    for index, key in enumerate(raw):
        if not isinstance(key, dict):
            continue
        for field in ("kid", "kty", "use", "alg"):
            if not key.get(field):
                issues.append(
                    ProtocolReadinessIssue(
                        field=f"signing_keys[{index}].{field}",
                        severity="warning",
                        message=f"Signing key is missing {field}.",
                        fix="Publish complete JWK metadata for message verification.",
                    )
                )
    return issues


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
    if not isinstance(data, dict) or data.get("version") not in SUPPORTED_UCP_VERSIONS:
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
    for path in (CURRENT_PLATFORM_PROFILE_PATH, PLATFORM_PROFILE_PATH):
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


__all__ = [
    "PINNED_UCP_VERSION",
    "CURRENT_UCP_VERSION",
    "SUPPORTED_UCP_VERSIONS",
    "REQUIRED_CAPABILITIES",
    "UcpProfileReport",
    "load_schema_store",
    "load_platform_capabilities",
    "validate_ucp_profile",
]
