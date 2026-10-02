import { createHmac } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const authMock = vi.hoisted(() => vi.fn());
vi.mock("@clerk/nextjs/server", () => ({ auth: authMock }));

import { GET } from "./route";

const originalFetch = global.fetch;

function request(clientId = "client-1", pagination = "") {
  return new Request(
    `http://localhost/api/operator-conversation/runs/run-1/commands?client_id=${clientId}${pagination}`,
  );
}

describe("operator command records browser BFF", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_MODE", "clerk");
    vi.stubEnv(
      "OPERATOR_BFF_SIGNING_SECRET",
      "web-bff-test-secret-at-least-32-characters",
    );
    vi.stubEnv("OPERATOR_API_URL", "http://api.internal");
    authMock.mockReset();
    authMock.mockReturnValue({ userId: "clerk-user-1" });
    global.fetch = vi.fn().mockResolvedValue(
      Response.json({ contract: "operator-command-record-list.v1", records: [] }),
    );
  });

  it("forwards the opaque cursor and bounded page size", async () => {
    const response = await GET(request("client-1", "&cursor=opaque-page&limit=25"), {
      params: { runId: "run-1" },
    });

    expect(response.status).toBe(200);
    const [url] = vi.mocked(global.fetch).mock.calls[0];
    expect(url).toBe(
      "http://api.internal/conversation/operator/runs/run-1/commands?client_id=client-1&user_id=clerk-user-1&cursor=opaque-page&limit=25",
    );
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("reads run-bound durable command records with the signed browser identity", async () => {
    const response = await GET(request(), { params: { runId: "run-1" } });

    expect(response.status).toBe(200);
    const [url, init] = vi.mocked(global.fetch).mock.calls[0];
    expect(url).toBe(
      "http://api.internal/conversation/operator/runs/run-1/commands?client_id=client-1&user_id=clerk-user-1",
    );
    const headers = new Headers(init?.headers);
    const assertion = String(headers.get("x-operator-session-assertion"));
    const [encoded, signature] = assertion.split(".");
    expect(signature).toBe(
      createHmac("sha256", "web-bff-test-secret-at-least-32-characters")
        .update(encoded, "ascii")
        .digest("hex"),
    );
    const claims = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    expect(claims).toMatchObject({
      sub: "clerk-user-1",
      client_id: "client-1",
      run_id: "run-1",
      aud: "operator-conversation-api",
    });
  });

  it("fails closed without a browser identity or tenant selector", async () => {
    authMock.mockReturnValueOnce({ userId: null });
    const unauthenticated = await GET(request(), { params: { runId: "run-1" } });
    authMock.mockReturnValue({ userId: "clerk-user-1" });
    const missingTenant = await GET(
      new Request("http://localhost/api/operator-conversation/runs/run-1/commands"),
      { params: { runId: "run-1" } },
    );

    expect(unauthenticated.status).toBe(401);
    expect(missingTenant.status).toBe(400);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
