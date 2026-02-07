export function buildTenantStorageKey(
  prefix: string,
  userId?: string | null,
  clientId?: string | null,
): string {
  const userTag = userId || "anonymous";
  const clientTag = clientId ? `.${clientId}` : "";
  return `${prefix}.${userTag}${clientTag}`;
}

