# Debug Log: Open Risks / Watchlist

Purpose: track unresolved risks and monitoring items that could affect release stability.
Relationship: complements `docs/debug/incidents-fixed.md`.

---

## 1) SQLite thread-local connection lifecycle in long-running dev sessions

- Status: mitigated, monitor.
- Why it matters:
  - Per-thread connections fixed cross-thread misuse, but long-lived worker/thread churn can leave stale connection entries if runtime behavior changes.
- Trigger indicators:
  - New intermittent DB errors under concurrency.
  - Unexpected growth of DB file locks / write contention symptoms.
- Current mitigation:
  - Thread-local connection model in `shared/db/connection.py`.
  - Registry cleanup on `set_database_path`.
- Validation checks:
  1. Run repeated tenant switching + admin product listing + simulation fetches.
  2. Watch backend logs for `sqlite3.InterfaceError` / `SystemError`.

---

## 2) Legacy localStorage fallback paths

- Status: intentional temporary compatibility; cleanup pending.
- Why it matters:
  - Legacy fallback keys can mask stale data if not eventually removed.
- Trigger indicators:
  - User reports old data reappearing after upgrade/migration.
- Current mitigation:
  - Tenant-scoped primary keys with fallback read support.
- Validation checks:
  1. Fresh browser profile: verify only scoped keys are used.
  2. Existing profile with old keys: verify one-time restore then scoped writes.
- Planned follow-up:
  - Add migration version flag and remove fallback after one release cycle.

---

## 3) Missing dependency for full backend test collection in some environments

- Status: environment-dependent.
- Why it matters:
  - Test collection can fail when optional providers (e.g., Gemini SDK) are absent.
- Trigger indicators:
  - `ModuleNotFoundError` during `pytest` collection.
- Current mitigation:
  - Focused tests and route-level checks when optional deps unavailable.
- Validation checks:
  1. CI test job with full optional deps installed.
  2. Local quick test profile without optional deps should still run core tests via markers or optional import guards.
- Planned follow-up:
  - Gate optional provider imports behind lazy loading or feature flags in tests.

---

## 4) Multi-surface state consistency (history + page local state + tenant context)

- Status: improved, monitor.
- Why it matters:
  - App has multiple coordinated states (tenant selection, history drawer, page drafts).
- Trigger indicators:
  - Wrong session/entity shown after tenant switch.
  - Deleted items still visible in one surface.
- Current mitigation:
  - Tenant-scoped keys and history bulk-delete wiring.
- Validation checks:
  1. Tenant switch with open history drawer.
  2. Bulk delete across chat/simulation/experiment and verify immediate UI consistency.
  3. Hard refresh behavior per page.

---

## 5) API contract drift risk (frontend helper paths vs backend routes)

- Status: recurring risk in fast iteration.
- Why it matters:
  - UI 404s appear when helper paths diverge from route prefixes.
- Trigger indicators:
  - Repeated `API error 404` in panels that previously worked.
- Current mitigation:
  - Manual fixes when discovered.
- Validation checks:
  1. Route smoke test for critical surfaces:
     - admin llm config
     - experiments list/create/run
     - validation create/run/log
     - overview summary/timeseries
2. Add lightweight contract tests for helper path map.

---

## 7) RBAC enforcement still admin-heavy

- Status: partially mitigated.
- Why it matters:
  - Multi-tenant isolation is in place, but most privileged operations still rely on admin checks rather than tenant role checks.
- Trigger indicators:
  - Need to expose client-scoped operator actions to non-admin users.
- Current mitigation:
  - Added reusable RBAC hook functions:
    - `has_client_role(...)`
    - `require_client_role(...)`
  - Current admin operations remain admin-only.
- Validation checks:
  1. Add route-level tests for client-role gated endpoints once first non-admin operation is introduced.
  2. Ensure role comparisons are normalized/lowercase.
- Planned follow-up:
  - Introduce first client-role-protected endpoint and cover with API tests.

---

## 6) Browser extension/UI artifacts (spellcheck underlines, native select overlays)

- Status: non-blocking, UX-noise.
- Why it matters:
  - Can be mistaken for app defects during demos.
- Trigger indicators:
  - Red squiggles in text inputs.
  - Native select tooltips/menus that look inconsistent.
- Current mitigation:
  - Some UI simplifications already applied.
- Validation checks:
  1. Demo pass in clean browser profile/incognito.
  2. Confirm no functional errors in console for those interactions.

---

## Pre-release gate for this watchlist

1. Run tenant-switch smoke script covering all pages.
2. Run API route smoke checks (backend up, expected 200/4xx only).
3. Run frontend lint and targeted backend tests.
4. Perform one clean-browser demo pass (no cached legacy keys).
