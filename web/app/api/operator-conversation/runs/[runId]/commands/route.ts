import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import { isMockAuthEnabled } from "@/lib/auth-mode";
import {
  createOperatorSessionAssertion,
  OPERATOR_ASSERTION_HEADER,
} from "@/lib/server/operatorSession";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: { runId: string } };

export async function GET(request: Request, { params }: RouteContext): Promise<Response> {
  const userId = authenticatedUserId();
  if (!userId) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }
  const browserQuery = new URL(request.url).searchParams;
  const clientId = browserQuery.get("client_id")?.trim() || "";
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
  const query = new URLSearchParams({ client_id: clientId, user_id: userId });
  const cursor = browserQuery.get("cursor")?.trim();
  const limit = browserQuery.get("limit")?.trim();
  if (cursor) query.set("cursor", cursor);
  if (limit) query.set("limit", limit);
  const upstream = await fetch(
    `${operatorApiBase()}/conversation/operator/runs/${encodeURIComponent(params.runId)}/commands?${query.toString()}`,
    {
      method: "GET",
      cache: "no-store",
      signal: request.signal,
      headers: { [OPERATOR_ASSERTION_HEADER]: assertion },
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
