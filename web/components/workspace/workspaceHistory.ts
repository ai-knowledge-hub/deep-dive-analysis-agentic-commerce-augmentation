import type { WorkspaceHistory, WorkspaceTurn } from "../../lib/workspace";
function orderedTurns(previous: WorkspaceTurn[], incoming: WorkspaceTurn[]) {
  // Recorded answers keep their original provenance when progress is refreshed.
  const turns = new Map(incoming.map((turn) => [turn.id, turn]));
  previous.forEach((turn) => turns.set(turn.id, turn));
  return [...turns.values()].sort((a, b) => a.id - b.id);
}
export function refreshWorkspaceHistory(current: WorkspaceHistory | null, next: WorkspaceHistory) {
  if (current?.session_id !== next.session_id) return next;
  const nextIds = new Set(next.turns.map((turn) => turn.id));
  const overlapping = current.turns.some((turn) => nextIds.has(turn.id));
  const retainedOlder = overlapping && current.turns.some((turn) => turn.id < (next.turns[0]?.id ?? Infinity));
  return { ...next, turns: orderedTurns(current.turns, next.turns),
    turns_has_more: retainedOlder ? current.turns_has_more : next.turns_has_more,
    turns_before_id: retainedOlder ? current.turns_before_id : next.turns_before_id };
}
export function prependWorkspaceHistory(current: WorkspaceHistory | null, page: WorkspaceHistory, id: string, before: number) {
  if (current?.session_id !== id || current.turns_before_id !== before) return current;
  return { ...current, turns: orderedTurns(current.turns, page.turns), turns_has_more: page.turns_has_more, turns_before_id: page.turns_before_id };
}
