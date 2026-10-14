import { createHmac, randomUUID } from "node:crypto";

export type WorkspaceOperation = "message" | "read" | "list" | "open" | "confirm";
export function createWorkspaceAssertion(userId: string, clientId: string, sessionId: string,
  operation: WorkspaceOperation, proposalId = "", proposalDigest = "", now = Math.floor(Date.now() / 1000)) {
  const secret = operation === "confirm" ? process.env.OPERATOR_COMMAND_BFF_SIGNING_SECRET : process.env.OPERATOR_BFF_SIGNING_SECRET;
  if (!secret || secret.length < 32) throw new Error("Workspace signing unavailable");
  if ([userId, clientId, sessionId].some((v) => !v.trim() || v.length > 256)) throw new Error("Invalid workspace identity");
  const payload = { schema_version: 1, aud: operation === "confirm" ? "operator-run-creation-api" : "operator-workspace-api",
    iss: "operator-workspace-web-bff", sub: userId, client_id: clientId, session_id: sessionId,
    operation, proposal_id: proposalId, proposal_digest: proposalDigest, iat: now, exp: now + 30, jti: randomUUID() };
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${encoded}.${createHmac("sha256", secret).update(encoded, "ascii").digest("hex")}`;
}
