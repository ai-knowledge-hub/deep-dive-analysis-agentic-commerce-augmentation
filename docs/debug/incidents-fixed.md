# Debug Log: Fixed Incidents (Release Prep)

Purpose: compact memory for recurring failure patterns and fixes applied in this codebase.
Scope: incidents discovered during iterative dev/test in this cycle and already fixed.

---

## 1) Admin tenant context mismatch (UI showed Acme while sidebar was Adidas)

- Symptom:
  - Admin onboarding cards did not match sidebar tenant selector.
  - Admin defaulted to first client in list.
- Root cause:
  - `web/app/admin/page.tsx` was managing local `activeClientId/BrandId/ProductId` independently of `useTenant`.
- Fix:
  - Wired admin state to tenant context (`useTenant`) both directions.
  - On load: prefer tenant-selected client/brand/product over first-item fallback.
  - On admin dropdown changes: also update tenant provider state.
- Key files:
  - `web/app/admin/page.tsx`
- Pattern:
  - Any page that owns client/brand/product state must be explicitly synchronized with `TenantProvider`.

---

## 2) Cross-tenant localStorage bleed (draft/state reused across clients)

- Symptom:
  - After switching tenant, stale drafts/simulation/alignment state could appear from another client.
- Root cause:
  - Several keys were user-scoped only (no client suffix), while API calls were tenant-scoped.
- Fix:
  - Introduced tenant-scoped key builder:
    - `web/lib/storage.ts` -> `buildTenantStorageKey(prefix, userId, clientId)`
  - Migrated localStorage keys to `user + client` scope for:
    - chat simulation payload
    - simulation page payload/latest payload
    - alignment snapshot
    - experiments draft
  - Added legacy fallback reads for seamless migration.
- Key files:
  - `web/lib/storage.ts`
  - `web/app/page.tsx`
  - `web/app/simulation/page.tsx`
  - `web/app/alignment/page.tsx`
  - `web/app/experiments/page.tsx`
- Pattern:
  - If backend is tenant-scoped, frontend caches must be tenant-scoped too.

---

## 3) SQLite `InterfaceError: bad parameter or other API misuse` on admin list products

- Symptom:
  - API error path:
    - `/brands/{brand_id}/products`
    - stack ended in `infrastructure/db/clients.py:list_products`
  - intermittent `sqlite3.InterfaceError`.
- Root cause:
  - Shared singleton sqlite connection used across worker threads (`check_same_thread=False`) caused unsafe concurrent access.
- Fix:
  - Switched to per-thread sqlite connections with thread-local storage.
  - Added connection registry cleanup on `set_database_path`.
- Key files:
  - `shared/db/connection.py`
- Pattern:
  - For SQLite + threaded FastAPI workers, avoid one global connection object.

---

## 4) Admin model gateway 404 (`/admin/llm/config`)

- Symptom:
  - UI displayed `API error 404` for model gateway.
- Root cause:
  - Frontend was using wrong route shape; active routes are under `/llm/config`.
- Fix:
  - Gateway calls aligned to existing backend endpoints.
- Key files:
  - `web/lib/api.ts` (LLM config helpers)
  - `api/routes/...` (route surface already `/llm/config*`)
- Pattern:
  - Keep one canonical route prefix map for frontend API helpers.

---

## 5) Experiments page state persistence confusion after refresh

- Symptom:
  - Mixed behavior: partial UI state retained, form values reset, loop toggles inconsistent.
- Root cause:
  - Restore flow and persisted fields were not consistently scoped/managed.
- Fix:
  - Added explicit restore prompt flow.
  - Unified persistence fields and cleanup behavior.
  - Later tenant-scoped keys removed cross-client restoration contamination.
- Key files:
  - `web/app/experiments/page.tsx`
- Pattern:
  - Restore UX must be explicit (prompt + clear scope + deterministic fields list).

---

## 6) Validation/Experiments coupling confusion

- Symptom:
  - Validation controls duplicated or conceptually split between pages.
  - Hard to interpret synthetic vs observed signals.
- Root cause:
  - Incomplete decoupling and mixed UI responsibilities.
- Fix:
  - Validation moved to dedicated validation page structure:
    - synthetic signal section
    - observed reality signal section
  - Experiments page reduced to experiment execution concerns.
- Key files:
  - `web/app/experiments/page.tsx`
  - `web/app/validation/page.tsx`
- Pattern:
  - Keep lifecycle stages in separate surfaces when their evidence type differs.

---

## 7) Lint instability from non-memoized derived values / hook deps

- Symptom:
  - Repeated `react-hooks/exhaustive-deps` warnings.
- Root cause:
  - Derived arrays/objects created outside `useMemo`; missing effect deps.
- Fix:
  - Memoized derived values in `alignment`/`overview`.
  - Corrected deps in `TenantProvider`.
- Key files:
  - `web/app/alignment/page.tsx`
  - `web/app/overview/page.tsx`
  - `web/components/tenant/TenantProvider.tsx`
- Pattern:
  - Treat lint warnings as correctness warnings in stateful pages.

---

## Pre-release checks to re-run

1. Tenant switch matrix:
   - switch client/brand/product in sidebar
   - verify Chat/Alignment/Evidence/Simulation/Experiments/Validation/Admin all stay in tenant scope
2. Storage isolation:
   - create drafts in tenant A
   - switch to tenant B
   - verify no draft/state bleed
3. SQLite concurrency smoke:
   - run parallel UI actions (admin list products + simulation listing + history operations)
   - verify no `InterfaceError`/`SystemError` from sqlite layer
4. Route contract checks:
   - ensure frontend helpers still match backend path prefixes (`/llm/config`, `/validation/*`, `/experiments/*`)

