import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import {
  createOperatorSessionAssertion,
  OPERATOR_ASSERTION_HEADER,
} from "@/lib/server/operatorSession";
import { isMockAuthEnabled } from "@/lib/auth-mode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: { runId: string } };

export async function POST(request: Request, { params }: RouteContext): Promise<Response> {
  const userId = authenticatedUserId();
  if (!userId) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }
  let body: Record<string, unknown>;
  try {
    const parsed: unknown = await request.json();
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("invalid body");
    }
    body = parsed as Record<string, unknown>;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON request" }, { status: 400 });
  }
  const clientId = typeof body.client_id === "string" ? body.client_id.trim() : "";
  if (!clientId) {
    return NextResponse.json({ detail: "client_id is required" }, { status: 400 });
  }

  let assertion: string;
  try {
    assertion = createOperatorSessionAssertion(userId, clientId, params.runId);
  } catch {
    return NextResponse.json(
      { detail: "Operator conversation authentication is unavailable" },
      { status: 503 },
    );
  }
  const apiBase = operatorApiBase();
  const upstream = await fetch(
    `${apiBase}/conversation/operator/runs/${encodeURIComponent(params.runId)}/stream`,
    {
      method: "POST",
      cache: "no-store",
      signal: request.signal,
      headers: {
        "Content-Type": "application/json",
        [OPERATOR_ASSERTION_HEADER]: assertion,
      },
      body: JSON.stringify({ ...body, user_id: userId, client_id: clientId }),
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
