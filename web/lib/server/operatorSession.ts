import { createHmac, randomUUID } from "node:crypto";

export const OPERATOR_ASSERTION_HEADER = "X-Operator-Session-Assertion";
export const OPERATOR_ASSERTION_AUDIENCE = "operator-conversation-api";
export const OPERATOR_ASSERTION_ISSUER = "operator-conversation-web-bff";
export const OPERATOR_ASSERTION_SCHEMA_VERSION = 1;
const ASSERTION_TTL_SECONDS = 30;

export function createOperatorSessionAssertion(
  userId: string,
  clientId: string,
  runId: string,
  nowSeconds = Math.floor(Date.now() / 1000),
): string {
  const secret = process.env.OPERATOR_BFF_SIGNING_SECRET?.trim();
  if (!secret || secret.length < 32) {
    throw new Error("operator BFF signing is not configured");
  }
  const payload = {
    schema_version: OPERATOR_ASSERTION_SCHEMA_VERSION,
    aud: OPERATOR_ASSERTION_AUDIENCE,
    iss: OPERATOR_ASSERTION_ISSUER,
    sub: requiredIdentity("userId", userId),
    client_id: requiredIdentity("clientId", clientId),
    run_id: requiredIdentity("runId", runId),
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
  if (!normalized || normalized.length > 256) {
    throw new Error(`${field} is invalid`);
  }
  return normalized;
}
