import { createHmac } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const authMock = vi.hoisted(() => vi.fn());
vi.mock("@clerk/nextjs/server", () => ({ auth: authMock }));

import { POST } from "./route";

const originalFetch = global.fetch;
const digest = "a".repeat(64);

function request(body: Record<string, unknown>) {
  return new Request(
    "http://localhost/api/operator-conversation/runs/run-1/commands/proposal-1/confirm",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

describe("operator command browser BFF", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_MODE", "clerk");
    vi.stubEnv(
      "OPERATOR_COMMAND_BFF_SIGNING_SECRET",
      "operator-command-web-secret-at-least-32",
    );
    vi.stubEnv("OPERATOR_API_URL", "http://api.internal");
    authMock.mockReset();
    authMock.mockReturnValue({ userId: "clerk-user-1" });
    global.fetch = vi.fn().mockResolvedValue(
      Response.json({ contract: "operator-command-confirmation.v1" }),
    );
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("binds one human session to one exact pause proposal", async () => {
    const response = await POST(
      request({
        client_id: "client-1",
        proposal_digest: digest,
        user_id: "forged-user",
      }),
      { params: { runId: "run-1", proposalId: "proposal-1" } },
    );

    expect(response.status).toBe(200);
    const [url, init] = vi.mocked(global.fetch).mock.calls[0];
    expect(url).toBe(
      "http://api.internal/conversation/operator/runs/run-1/commands/proposal-1/confirm",
    );
    expect(JSON.parse(String(init?.body))).toEqual({
      client_id: "client-1",
      user_id: "clerk-user-1",
      proposal_digest: digest,
    });
    const headers = new Headers(init?.headers);
    expect(headers.has("authorization")).toBe(false);
    expect(headers.has("x-operator-session-assertion")).toBe(false);
    const assertion = String(headers.get("x-operator-command-assertion"));
    const [encoded, signature] = assertion.split(".");
    const expected = createHmac(
      "sha256",
      "operator-command-web-secret-at-least-32",
    )
      .update(encoded, "ascii")
      .digest("hex");
    expect(signature).toBe(expected);
    const claims = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    expect(claims).toMatchObject({
      aud: "operator-command-api",
      iss: "operator-command-web-bff",
      sub: "clerk-user-1",
      client_id: "client-1",
      run_id: "run-1",
      proposal_id: "proposal-1",
      proposal_digest: digest,
      command_type: "pause",
    });
    expect(claims.exp - claims.iat).toBe(30);
  });

  it("fails closed without a signed-in user", async () => {
    authMock.mockReturnValue({ userId: null });

    const response = await POST(
      request({ client_id: "client-1", proposal_digest: digest }),
      { params: { runId: "run-1", proposalId: "proposal-1" } },
    );

    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("does not fall back to the read-only conversation signing secret", async () => {
    vi.stubEnv("OPERATOR_COMMAND_BFF_SIGNING_SECRET", "");
    vi.stubEnv("OPERATOR_BFF_SIGNING_SECRET", "read-only-secret-at-least-32-characters");

    const response = await POST(
      request({ client_id: "client-1", proposal_digest: digest }),
      { params: { runId: "run-1", proposalId: "proposal-1" } },
    );

    expect(response.status).toBe(503);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
