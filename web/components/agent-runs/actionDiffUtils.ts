export type DiffBlock = {
  added: { key: string; current: string }[];
  changed: { key: string; current: string; previous: string }[];
  removed: { key: string; previous: string }[];
};

export type TextDiffLine = { kind: "same" | "added" | "removed"; text: string };

export function formatJsonPreview(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? "");
  }
}

export function toFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

export function collectNumericValues(value: unknown, keys: Set<string>): number[] {
  if (!value || typeof value !== "object") return [];
  if (Array.isArray(value)) {
    return value.flatMap((item) => collectNumericValues(item, keys));
  }
  const entries = Object.entries(value as Record<string, unknown>);
  return entries.flatMap(([key, nested]) => {
    const direct = keys.has(key) ? toFiniteNumber(nested) : null;
    return [...(direct == null ? [] : [direct]), ...collectNumericValues(nested, keys)];
  });
}

export function keyDiffSummary(
  current: Record<string, unknown>,
  previous: Record<string, unknown>,
): { added: string[]; changed: string[]; removed: string[] } {
  const currentKeys = new Set(Object.keys(current));
  const previousKeys = new Set(Object.keys(previous));
  const added = [...currentKeys].filter((key) => !previousKeys.has(key));
  const removed = [...previousKeys].filter((key) => !currentKeys.has(key));
  const changed = [...currentKeys].filter((key) => {
    if (!previousKeys.has(key)) return false;
    const nextValue = formatJsonPreview(current[key]);
    const prevValue = formatJsonPreview(previous[key]);
    return nextValue !== prevValue;
  });
  return { added, changed, removed };
}

export function shortKeyList(keys: string[], max = 6): string {
  if (keys.length === 0) return "None";
  const sliced = keys.slice(0, max);
  return keys.length > max ? `${sliced.join(", ")} +${keys.length - max} more` : sliced.join(", ");
}

export function safeRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

export function buildDetailedDiffEntries(
  current: Record<string, unknown>,
  previous: Record<string, unknown>,
): DiffBlock {
  const currentKeys = new Set(Object.keys(current));
  const previousKeys = new Set(Object.keys(previous));
  const added = [...currentKeys]
    .filter((key) => !previousKeys.has(key))
    .map((key) => ({
      key,
      current: formatJsonPreview(current[key]),
    }));
  const removed = [...previousKeys]
    .filter((key) => !currentKeys.has(key))
    .map((key) => ({
      key,
      previous: formatJsonPreview(previous[key]),
    }));
  const changed = [...currentKeys]
    .filter((key) => previousKeys.has(key))
    .map((key) => ({
      key,
      current: formatJsonPreview(current[key]),
      previous: formatJsonPreview(previous[key]),
    }))
    .filter((entry) => entry.current !== entry.previous);
  return { added, changed, removed };
}

export function buildTextDiffLines(previousText: string, currentText: string): TextDiffLine[] {
  const before = previousText.split("\n");
  const after = currentText.split("\n");
  const rows: TextDiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < before.length && j < after.length) {
    if (before[i] === after[j]) {
      rows.push({ kind: "same", text: after[j] });
      i += 1;
      j += 1;
      continue;
    }
    if (i + 1 < before.length && before[i + 1] === after[j]) {
      rows.push({ kind: "removed", text: before[i] });
      i += 1;
      continue;
    }
    if (j + 1 < after.length && before[i] === after[j + 1]) {
      rows.push({ kind: "added", text: after[j] });
      j += 1;
      continue;
    }
    rows.push({ kind: "removed", text: before[i] });
    rows.push({ kind: "added", text: after[j] });
    i += 1;
    j += 1;
  }
  while (i < before.length) {
    rows.push({ kind: "removed", text: before[i] });
    i += 1;
  }
  while (j < after.length) {
    rows.push({ kind: "added", text: after[j] });
    j += 1;
  }
  return rows;
}

export function getStringDiffCandidates(
  current: Record<string, unknown>,
  previous: Record<string, unknown>,
): { key: string; current: string; previous: string; lines: TextDiffLine[] }[] {
  const keys = Object.keys(current).filter((key) => key in previous);
  return keys
    .map((key) => {
      const next = current[key];
      const prev = previous[key];
      if (typeof next !== "string" || typeof prev !== "string") return null;
      if (next === prev) return null;
      const isCopyLike =
        next.length >= 40 ||
        prev.length >= 40 ||
        next.includes("\n") ||
        prev.includes("\n");
      if (!isCopyLike) return null;
      return {
        key,
        current: next,
        previous: prev,
        lines: buildTextDiffLines(prev, next),
      };
    })
    .filter(Boolean) as { key: string; current: string; previous: string; lines: TextDiffLine[] }[];
}

export function budgetSeverity(
  used: number,
  limit: number | null,
  percent: number | null,
): "ok" | "warn" | "danger" {
  if (limit == null) return "ok";
  if (used >= limit) return "danger";
  if ((percent ?? 0) >= 80) return "warn";
  return "ok";
}
