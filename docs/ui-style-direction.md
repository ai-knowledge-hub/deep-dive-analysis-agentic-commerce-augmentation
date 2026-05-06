# UI Style Direction

The control plane should move away from accidental bento density: nested cards,
repeated borders, and badges used as layout. The target style is **Swiss Control
Plane + Minimalist Density**.

## Principles

1. Use grid, type, and spacing before borders.
2. Reserve cards for selectable or actionable objects.
3. Prefer flat sections for status, summaries, and metadata.
4. Use one accent channel for attention; calm states should stay quiet.
5. Keep the lab available, but make the agentic control plane feel primary.

## Practical Rules

- A page may have a primary surface, but avoid card-inside-card nesting.
- Dense operational data should use lists or tables, not stacked panels.
- Badges should describe state, not become the main visual structure.
- Dividers should be lighter than borders around every container.
- Whitespace should separate sections before another box is introduced.

## First Adoption Area

Start with `Runs`, because it currently carries the most nested operational UI.
The first implementation uses flatter primitives for the run rail and selected
run execution summary before applying the same language to `Inbox`,
`Interventions`, and `Learnings`.
