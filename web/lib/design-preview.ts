export function workspacePreviewEnabled(
  mode: string | undefined,
  flag: string | undefined,
): boolean {
  return mode === "development" || mode === "test" || flag === "true";
}
