import { createHmac } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const authMock = vi.hoisted(() => vi.fn());

vi.mock("@clerk/nextjs/server", () => ({ auth: authMock }));

import { POST } from "./route";

const originalFetch = global.fetch;

function request(body: Record<string, unknown>) {
  return new Request("http://localhost/api/operator-conversation/runs/run-1/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("operator conversation browser BFF", () => {
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
      new Response("event: operator_conversation\ndata: {}\n\n", {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("derives browser identity from Clerk and forwards a narrow signed assertion", async () => {
    const response = await POST(
      request({
        message: "Explain this run",
        client_id: "client-1",
        user_id: "forged-browser-user",
      }),
      { params: { runId: "run-1" } },
    );

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledOnce();
    const [url, init] = vi.mocked(global.fetch).mock.calls[0];
    expect(url).toBe("http://api.internal/conversation/operator/runs/run-1/stream");
    const forwarded = JSON.parse(String(init?.body));
    expect(forwarded.user_id).toBe("clerk-user-1");
    expect(forwarded.client_id).toBe("client-1");
    const headers = new Headers(init?.headers);
    expect(headers.has("authorization")).toBe(false);
    const assertion = headers.get("x-operator-session-assertion");
    expect(assertion).toBeTruthy();
    const [encoded, signature] = String(assertion).split(".");
    const expected = createHmac(
      "sha256",
      "web-bff-test-secret-at-least-32-characters",
    )
      .update(encoded, "ascii")
      .digest("hex");
    expect(signature).toBe(expected);
    const claims = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    expect(claims).toMatchObject({
      schema_version: 1,
      aud: "operator-conversation-api",
      iss: "operator-conversation-web-bff",
      sub: "clerk-user-1",
      client_id: "client-1",
      run_id: "run-1",
    });
    expect(claims.exp - claims.iat).toBe(30);
  });

  it("uses the server-owned mock identity only in explicit mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_MODE", "mock");
    vi.stubEnv("NEXT_PUBLIC_MOCK_USER_ID", "mock-browser-user");

    await POST(request({ message: "Explain", client_id: "client-1" }), {
      params: { runId: "run-1" },
    });

    expect(authMock).not.toHaveBeenCalled();
    const [, init] = vi.mocked(global.fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body)).user_id).toBe("mock-browser-user");
  });

  it("fails closed before contacting the API without a signed-in browser user", async () => {
    authMock.mockReturnValue({ userId: null });

    const response = await POST(request({ message: "Explain", client_id: "client-1" }), {
      params: { runId: "run-1" },
    });

    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
