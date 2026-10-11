import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import { isMockAuthEnabled } from "@/lib/auth-mode";
import {
  createOperatorCommandAssertion,
  OPERATOR_COMMAND_ASSERTION_HEADER,
} from "@/lib/server/operatorCommandSession";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: { runId: string; proposalId: string } };

export async function POST(request: Request, { params }: RouteContext): Promise<Response> {
  const userId = authenticatedUserId();
  if (!userId) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  let body: Record<string, unknown>;
  try {
    const parsed: unknown = await request.json();
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
    body = parsed as Record<string, unknown>;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON request" }, { status: 400 });
  }
  const clientId = typeof body.client_id === "string" ? body.client_id.trim() : "";
  const proposalDigest =
    typeof body.proposal_digest === "string" ? body.proposal_digest.trim() : "";
  if (!clientId || !proposalDigest) {
    return NextResponse.json(
      { detail: "client_id and proposal_digest are required" },
      { status: 400 },
    );
  }

  const commandType = body.command_type ?? "pause";
  if (commandType !== "pause" && commandType !== "resume" && commandType !== "cancel" && commandType !== "approve" && commandType !== "reject" && commandType !== "retry" && commandType !== "reconcile_effect") {
    return NextResponse.json({ detail: "Unsupported command type" }, { status: 400 });
  }
  const reconcile = commandType === "reconcile_effect";
  const effectExecutionId = typeof body.effect_execution_id === "string" ? body.effect_execution_id.trim() : "";
  if (reconcile && (!effectExecutionId || effectExecutionId.length > 256)) return NextResponse.json({ detail: "An exact effect_execution_id is required" }, { status: 400 });
  const retry = commandType === "retry";
  if (retry && body.retry_strategy !== "same_action") return NextResponse.json({ detail: "An exact retry strategy is required" }, { status: 400 });
  const review = commandType === "approve" || commandType === "reject";
  const actionId = typeof body.action_id === "string" ? body.action_id.trim() : "";
  if ((review || retry || reconcile) && (!actionId || actionId.length > 256)) {
    return NextResponse.json({ detail: "An exact action_id is required" }, { status: 400 });
  }
  let assertion: string;
  try {
    assertion = createOperatorCommandAssertion(
      userId,
      clientId,
      params.runId,
      params.proposalId,
      proposalDigest,
      commandType,
      undefined,
      review || retry || reconcile ? actionId : undefined,
      reconcile ? effectExecutionId : undefined,
    );
  } catch {
    return NextResponse.json(
      { detail: "Operator command authentication is unavailable" },
      { status: 503 },
    );
  }
  const upstream = await fetch(
    `${operatorApiBase()}/conversation/operator/runs/${encodeURIComponent(params.runId)}/commands/${encodeURIComponent(params.proposalId)}/confirm`,
    {
      method: "POST",
      cache: "no-store",
      signal: request.signal,
      headers: {
        "Content-Type": "application/json",
        [OPERATOR_COMMAND_ASSERTION_HEADER]: assertion,
      },
      body: JSON.stringify({
        client_id: clientId,
        user_id: userId,
        proposal_digest: proposalDigest,
        command_type: commandType,
        ...(reconcile ? { effect_execution_id: effectExecutionId } : {}),
        ...(retry ? { retry_strategy: "same_action" } : {}),
        ...(review || retry || reconcile ? { action_id: actionId } : {}),
      }),
    },
  );
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    },
  });
}

function authenticatedUserId(): string | null {
  if (isMockAuthEnabled()) {
    return process.env.NEXT_PUBLIC_MOCK_USER_ID?.trim() || "mock-user-local";
  }
  return auth().userId;
}

function operatorApiBase(): string {
  const configured =
    process.env.OPERATOR_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return configured.replace(/\/$/, "");
}
