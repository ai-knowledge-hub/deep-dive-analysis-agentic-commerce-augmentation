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

  it("binds exact retry source and strategy in its own audience and replaces body identity", async () => {
    const response = await POST(request({ client_id: "client-1", proposal_digest: digest, command_type: "retry", action_id: "failed-action", retry_strategy: "same_action", user_id: "forged" }), { params: { runId: "run-1", proposalId: "proposal-1" } });
    expect(response.status).toBe(200);
    const [, init] = vi.mocked(global.fetch).mock.calls[0];
    const assertion = new Headers(init?.headers).get("x-operator-command-assertion")!;
    const claims = JSON.parse(Buffer.from(assertion.split(".")[0], "base64url").toString("utf8"));
    expect(claims).toMatchObject({ schema_version: 3, aud: "operator-retry-api", iss: "operator-retry-web-bff", sub: "clerk-user-1", action_id: "failed-action", command_type: "retry", retry_strategy: "same_action", proposal_id: "proposal-1", proposal_digest: digest });
    expect(JSON.parse(String(init?.body))).toMatchObject({ user_id: "clerk-user-1", action_id: "failed-action", command_type: "retry", retry_strategy: "same_action" });
  });
  it.each([undefined, "last_safe_checkpoint", "create_recovery_action"])("rejects an unsupported retry strategy %s before minting authority", async (strategy) => {
    const response = await POST(request({ client_id: "client-1", proposal_digest: digest, command_type: "retry", action_id: "failed-action", retry_strategy: strategy }), { params: { runId: "run-1", proposalId: "proposal-1" } });
    expect(response.status).toBe(400); expect(global.fetch).not.toHaveBeenCalled();
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
      command_type: "pause",
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

  it.each(["resume", "cancel"])("binds %s explicitly in signed claims and upstream body", async (commandType) => {
    await POST(request({ client_id: "client-1", proposal_digest: digest, command_type: commandType }),
      { params: { runId: "run-1", proposalId: "proposal-1" } });
    const [, init] = vi.mocked(global.fetch).mock.calls[0];
    const assertion = new Headers(init?.headers).get("x-operator-command-assertion")!;
    const claims = JSON.parse(Buffer.from(assertion.split(".")[0], "base64url").toString("utf8"));
    expect(claims.command_type).toBe(commandType);
    expect(JSON.parse(String(init?.body)).command_type).toBe(commandType);
  });


  it.each(["approve", "reject"])("binds exact %s action in a separate signed audience", async (commandType) => {
    const response = await POST(request({ client_id: "client-1", proposal_digest: digest, command_type: commandType, action_id: "action-1", user_id: "forged" }), { params: { runId: "run-1", proposalId: "proposal-1" } });
    expect(response.status).toBe(200);
    const [, init] = vi.mocked(global.fetch).mock.calls[0];
    const assertion = new Headers(init?.headers).get("x-operator-command-assertion")!;
    const claims = JSON.parse(Buffer.from(assertion.split(".")[0], "base64url").toString("utf8"));
    expect(claims).toMatchObject({ schema_version: 2, aud: "operator-action-review-api", iss: "operator-action-review-web-bff", sub: "clerk-user-1", action_id: "action-1", command_type: commandType, proposal_id: "proposal-1", proposal_digest: digest });
    expect(JSON.parse(String(init?.body))).toMatchObject({ user_id: "clerk-user-1", action_id: "action-1", command_type: commandType });
  });
  it.each(["approve", "reject"])("rejects %s without an exact action before minting authority", async (commandType) => {
    const response = await POST(request({ client_id: "client-1", proposal_digest: digest, command_type: commandType }), { params: { runId: "run-1", proposalId: "proposal-1" } });
    expect(response.status).toBe(400); expect(global.fetch).not.toHaveBeenCalled();
  });
  it("rejects commands outside the closed conversational command boundary", async () => {
    const result = await POST(request({ client_id: "client-1", proposal_digest: digest, command_type: "start" }),
      { params: { runId: "run-1", proposalId: "proposal-1" } });
    expect(result.status).toBe(400);
    expect(global.fetch).not.toHaveBeenCalled();
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
