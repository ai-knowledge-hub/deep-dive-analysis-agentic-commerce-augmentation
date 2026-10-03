import { createHmac, randomUUID } from "node:crypto";

export const OPERATOR_COMMAND_ASSERTION_HEADER = "X-Operator-Command-Assertion";
export const OPERATOR_COMMAND_ASSERTION_AUDIENCE = "operator-command-api";
export const OPERATOR_COMMAND_ASSERTION_ISSUER = "operator-command-web-bff";
export const OPERATOR_COMMAND_ASSERTION_SCHEMA_VERSION = 1;
const ASSERTION_TTL_SECONDS = 30;

export function createOperatorCommandAssertion(
  userId: string,
  clientId: string,
  runId: string,
  proposalId: string,
  proposalDigest: string,
  commandType: "pause" | "resume" | "cancel" = "pause",
  nowSeconds = Math.floor(Date.now() / 1000),
): string {
  const secret = process.env.OPERATOR_COMMAND_BFF_SIGNING_SECRET?.trim();
  if (!secret || secret.length < 32) {
    throw new Error("operator command BFF signing is not configured");
  }
  if (!/^[a-f0-9]{64}$/.test(proposalDigest)) {
    throw new Error("proposalDigest is invalid");
  }
  const payload = {
    schema_version: OPERATOR_COMMAND_ASSERTION_SCHEMA_VERSION,
    aud: OPERATOR_COMMAND_ASSERTION_AUDIENCE,
    iss: OPERATOR_COMMAND_ASSERTION_ISSUER,
    sub: requiredIdentity("userId", userId),
    client_id: requiredIdentity("clientId", clientId),
    run_id: requiredIdentity("runId", runId),
    proposal_id: requiredIdentity("proposalId", proposalId),
    proposal_digest: proposalDigest,
    command_type: commandType,
    iat: nowSeconds,
    exp: nowSeconds + ASSERTION_TTL_SECONDS,
    jti: randomUUID(),
  };
  const encoded = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  const signature = createHmac("sha256", secret).update(encoded, "ascii").digest("hex");
  return `${encoded}.${signature}`;
}

function requiredIdentity(field: string, value: string): string {
  const normalized = value.trim();
  if (!normalized || normalized.length > 256) throw new Error(`${field} is invalid`);
  return normalized;
}
