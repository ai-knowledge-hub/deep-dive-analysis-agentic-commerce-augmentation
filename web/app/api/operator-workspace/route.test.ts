import { createHmac } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const authMock = vi.hoisted(() => vi.fn());
vi.mock("@clerk/nextjs/server", () => ({ auth: authMock }));
import { POST } from "./route";
const originalFetch = global.fetch;
function request(body: object) { return new Request("http://localhost/api/operator-workspace", { method: "POST", body: JSON.stringify(body) }); }
beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_AUTH_MODE", "clerk"); vi.stubEnv("OPERATOR_API_URL", "http://api.internal");
  vi.stubEnv("OPERATOR_BFF_SIGNING_SECRET", "read-workspace-secret-with-at-least-32");
  vi.stubEnv("OPERATOR_COMMAND_BFF_SIGNING_SECRET", "confirm-workspace-secret-at-least-32");
  authMock.mockReturnValue({ userId: "authenticated-human" });
  global.fetch = vi.fn().mockResolvedValue(new Response("{}"));
});
afterEach(() => { global.fetch = originalFetch; vi.unstubAllEnvs(); });
describe("workspace browser authority", () => {
  it.each(["message", "read", "list", "open", "confirm"])("binds %s to server identity and exact scope", async (operation) => {
    const digest = "a".repeat(64);
    const response = await POST(request({ operation, client_id: "tenant", user_id: "forged", session_id: "session", run_id: "run", proposal_id: "proposal", proposal_digest: digest, message: "Improve commerce" }));
    expect(response.status).toBe(200);
    const [, init] = vi.mocked(global.fetch).mock.calls[0];
    const [encoded, signature] = String(new Headers(init?.headers).get("x-operator-workspace-assertion")).split(".");
    const claims = JSON.parse(Buffer.from(encoded, "base64url").toString());
    expect(claims.sub).toBe("authenticated-human"); expect(claims.operation).toBe(operation);
    expect(claims.session_id).toBe(operation === "list" ? "list" : operation === "open" ? "run" : "session");
    const secret = operation === "confirm" ? "confirm-workspace-secret-at-least-32" : "read-workspace-secret-with-at-least-32";
    expect(signature).toBe(createHmac("sha256", secret).update(encoded, "ascii").digest("hex"));
    expect(claims.aud).toBe(operation === "confirm" ? "operator-run-creation-api" : "operator-workspace-api");
    expect(JSON.parse(String(init?.body ?? "{}"))).not.toHaveProperty("user_id");
  });
  it("rejects anonymous, missing exact proposal and missing signer", async () => {
    authMock.mockReturnValue({ userId: null });
    expect((await POST(request({ operation: "message", client_id: "tenant" }))).status).toBe(401);
    authMock.mockReturnValue({ userId: "human" });
    expect((await POST(request({ operation: "confirm", client_id: "tenant", session_id: "session" }))).status).toBe(400);
    vi.stubEnv("OPERATOR_COMMAND_BFF_SIGNING_SECRET", "");
    expect((await POST(request({ operation: "confirm", client_id: "tenant", session_id: "session", proposal_id: "p", proposal_digest: "a".repeat(64) }))).status).toBe(503);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

it("forwards bounded older-history cursor within the authenticated session", async () => {
  authMock.mockReturnValue({ userId: "human" });
  const result = await POST(request({ operation: "read", client_id: "tenant", session_id: "session", before_turn_id: 5 }));
  expect(result.status).toBe(200);
  expect(String(vi.mocked(global.fetch).mock.calls.at(-1)?.[0])).toContain("/session?client_id=tenant&before_turn_id=5");
});
it.each([0, -1, 1.5, "5", 2 ** 53])("rejects unsafe history cursor %s before upstream access", async (cursor) => {
  authMock.mockReturnValue({ userId: "human" });
  expect((await POST(request({ operation: "read", client_id: "tenant", session_id: "session", before_turn_id: cursor }))).status).toBe(400);
  expect(global.fetch).not.toHaveBeenCalled();
});
