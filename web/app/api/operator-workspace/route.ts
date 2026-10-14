import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { isMockAuthEnabled } from "@/lib/auth-mode";
import { createWorkspaceAssertion, type WorkspaceOperation } from "@/lib/server/operatorWorkspaceSession";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const OPERATIONS = new Set(["message", "read", "list", "open", "confirm"]);

export async function POST(request: Request) {
  const userId = isMockAuthEnabled() ? process.env.NEXT_PUBLIC_MOCK_USER_ID?.trim() || "mock-user-local" : auth().userId;
  if (!userId) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  let body: Record<string, unknown>;
  try {
    body = await request.json();
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error("body");
  } catch { return NextResponse.json({ detail: "Invalid request" }, { status: 400 }); }
  const operation = String(body.operation) as WorkspaceOperation;
  const clientId = typeof body.client_id === "string" ? body.client_id.trim() : "";
  if (!OPERATIONS.has(operation) || !clientId) return NextResponse.json({ detail: "Operation and tenant required" }, { status: 400 });
  const sessionId = operation === "list" ? "list" : operation === "open" ? String(body.run_id ?? "") : String(body.session_id ?? "new");
  const before = body.before_turn_id;
  if (operation === "read" && before != null && (!Number.isSafeInteger(before) || Number(before) <= 0)) return NextResponse.json({ detail: "Invalid conversation page" }, { status: 400 });
  const proposalId = typeof body.proposal_id === "string" ? body.proposal_id : "";
  const digest = typeof body.proposal_digest === "string" ? body.proposal_digest : "";
  if (operation === "confirm" && (!proposalId || !/^[0-9a-f]{64}$/.test(digest))) return NextResponse.json({ detail: "Exact proposal required" }, { status: 400 });
  let assertion: string;
  try { assertion = createWorkspaceAssertion(userId, clientId, sessionId, operation, proposalId, digest); }
  catch { return NextResponse.json({ detail: "Workspace authentication unavailable" }, { status: 503 }); }
  const base = (process.env.OPERATOR_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const root = `${base}/conversation/operator/workspaces`;
  const path = operation === "list" ? `${root}?client_id=${encodeURIComponent(clientId)}` :
    operation === "read" ? `${root}/${encodeURIComponent(sessionId)}?client_id=${encodeURIComponent(clientId)}${before == null ? "" : `&before_turn_id=${before}`}` :
    operation === "confirm" ? `${root}/${encodeURIComponent(sessionId)}/proposals/${encodeURIComponent(proposalId)}/confirm` : `${root}/${operation}`;
  const payload = operation === "confirm" ? { client_id: clientId, proposal_digest: digest } :
    operation === "open" ? { client_id: clientId, run_id: body.run_id } :
    { client_id: clientId, session_id: body.session_id ?? null, experiment_id: body.experiment_id ?? null, message: body.message };
  try {
    const upstream = await fetch(path, { method: ["list", "read"].includes(operation) ? "GET" : "POST", cache: "no-store", signal: request.signal,
      headers: { "Content-Type": "application/json", "X-Operator-Workspace-Assertion": assertion },
      ...(["list", "read"].includes(operation) ? {} : { body: JSON.stringify(payload) }) });
    return new Response(upstream.body, { status: upstream.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  } catch { return NextResponse.json({ detail: "Workspace service unavailable" }, { status: 502 }); }
}
