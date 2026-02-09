# UX Consistency Release Checklist

Scope: `Experiments`, `Simulation`, `Evidence`, `Validation`

## Flow Structure

- [x] Each page has a top-level flow rail with numbered steps and current-step state.
- [x] Each page has a persistent "Next recommended action" block near the flow rail.
- [x] Primary CTA is visually dominant in the next-action block (`panel__actions--priority`).
- [x] Each page includes an "Outcome snapshot" style summary near the top.

## Step Hierarchy

- [x] Major sections follow a consistent pattern: panel title -> step subheading -> helper text.
- [x] High-importance decision sections use `panel__card--primary`.
- [x] Support/reference sections use `panel__card--secondary` or compact variants.
- [x] Top flow cards use separators between rail, next-action, and snapshot for readability.

## Progressive Disclosure

- [x] Dense secondary content is collapsed by default where appropriate:
  - [x] Experiments: setup extras, variant extras, history/recommendations.
  - [x] Evidence: advanced diagnostics blocks.
  - [x] Validation: variant comparison, external instructions, structured JSON.
  - [x] Simulation: secondary records panel toggle.

## CTA and Visual Priority

- [x] One clear primary CTA per active step section.
- [x] Secondary actions use ghost/less prominent styling.
- [x] Optional or reference actions are visually de-emphasized.

## Trust and Transparency Signals

- [x] Evidence includes source/freshness meta strip.
- [x] Validation includes synthetic + observed + readiness in one snapshot.
- [x] Experiments includes validation checkpoint and outcome snapshot.

## Mobile and Readability

- [x] Priority CTA groups stack full-width on mobile via shared responsive rules.
- [x] Dense blocks use helper text and spacing to reduce scanning load.
- [ ] Manual QA: run through each page at `768px` and `1280px` widths and confirm no clipped controls.

## Final Pre-Release QA

- [x] Type check passes: `cd web && pnpm tsc --noEmit`.
- [ ] Manual QA: verify primary CTA on each step always matches recommended action text.
- [ ] Manual QA: verify no duplicated "Step X" labels conflict in visible viewport.
- [ ] Manual QA: verify all "Open Validation/Open Experiments/Open Simulation" links route with expected context params.

