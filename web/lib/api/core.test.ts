import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearRegistryWriteToken,
  getRegistryWriteToken,
  registryWriteAuthHeaders,
  request,
  setRegistryWriteToken,
} from "./core";

describe("registry write auth helpers", () => {
  beforeEach(() => {
    const storage = new Map<string, string>();
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: (key: string) => storage.get(key) ?? null,
        setItem: (key: string, value: string) => storage.set(key, value),
        removeItem: (key: string) => storage.delete(key),
        clear: () => storage.clear(),
      },
      configurable: true,
    });
    vi.restoreAllMocks();
  });

  it("stores normalized registry-write bearer tokens locally", () => {
    setRegistryWriteToken("Bearer token-123 ");

    expect(getRegistryWriteToken()).toBe("token-123");
    expect(registryWriteAuthHeaders()).toEqual({
      Authorization: "Bearer token-123",
    });

    clearRegistryWriteToken();
    expect(getRegistryWriteToken()).toBeUndefined();
    expect(registryWriteAuthHeaders()).toBeUndefined();
  });

  it("preserves JSON headers when registry-write auth is supplied", async () => {
    setRegistryWriteToken("token-abc");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await request("/agent-runs/registry/harnesses/test-harness", {
      method: "PATCH",
      headers: registryWriteAuthHeaders(),
      body: JSON.stringify({ dry_run: true }),
    });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("content-type")).toBe("application/json");
    expect(headers.get("authorization")).toBe("Bearer token-abc");
  });
});
