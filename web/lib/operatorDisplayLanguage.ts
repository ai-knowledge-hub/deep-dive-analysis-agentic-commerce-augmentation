const OPERATOR_TEXT_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bpreflight\b/gi, "safety check"],
  [/\bcompensating action\b/gi, "recovery action"],
  [/\bcompensating proposal\b/gi, "recovery proposal"],
  [/\bcompensating\b/gi, "recovery"],
  [/\brollback\b/gi, "recovery path"],
  [/\bharness\b/gi, "execution posture"],
  [/\bregistry\b/gi, "tool contract"],
  [/\bposterior\b/gi, "confidence"],
  [/\bfrozen snapshots\b/gi, "saved evidence"],
  [/\bsnapshots?\b/gi, "saved evidence"],
  [/\bhypotheses\b/gi, "test ideas"],
  [/\bhypothesis\b/gi, "test idea"],
  [/\bcalibration\b/gi, "confidence check"],
  [/\bmemory artifact\b/gi, "saved context"],
  [/\bfingerprint\b/gi, "id"],
];

export function softenOperatorText(value?: string | null): string {
  let text = value || "";
  for (const [pattern, replacement] of OPERATOR_TEXT_REPLACEMENTS) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

export function formatOperatorActionName(value?: string | null): string {
  return softenOperatorText(String(value || "selected action").replaceAll("_", " "));
}
