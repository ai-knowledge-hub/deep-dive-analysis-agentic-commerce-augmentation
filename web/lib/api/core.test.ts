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
    clearRegistryWriteToken();
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: vi.fn(() => null),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      },
      configurable: true,
    });
    vi.restoreAllMocks();
  });

  it("stores normalized registry-write bearer tokens in memory only", () => {
    setRegistryWriteToken("Bearer token-123 ");

    expect(getRegistryWriteToken()).toBe("token-123");
    expect(registryWriteAuthHeaders()).toEqual({
      Authorization: "Bearer token-123",
    });
    expect(vi.mocked(window.localStorage.setItem)).not.toHaveBeenCalled();
    expect(vi.mocked(window.localStorage.getItem)).not.toHaveBeenCalled();

    clearRegistryWriteToken();
    expect(getRegistryWriteToken()).toBeUndefined();
    expect(registryWriteAuthHeaders()).toBeUndefined();
  });

  it("preserves JSON headers when registry-write auth is supplied", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
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
