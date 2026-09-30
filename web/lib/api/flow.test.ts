import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearRegistryWriteToken, setRegistryWriteToken } from "./core";
import { sendOperatorConversationMessageStream } from "./flow";

const originalFetch = global.fetch;

describe("operator conversation API handoff", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: vi.fn((key: string) => (key === "client_id" ? "client-1" : null)),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      },
      configurable: true,
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    clearRegistryWriteToken();
  });

  it("uses the same-origin authenticated BFF and never sends a registry credential", async () => {
    setRegistryWriteToken("external-agent-registry-token");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        'event: operator_conversation\ndata: {"session_id":"session-1"}\n\n',
        { status: 200, headers: { "Content-Type": "text/event-stream" } },
      ),
    );

    await sendOperatorConversationMessageStream(
      "run-1",
      "Explain this run",
      null,
      {},
    );

    const [url, init] = vi.mocked(global.fetch).mock.calls[0];
    expect(url).toBe("/api/operator-conversation/runs/run-1/stream");
    const headers = new Headers(init?.headers);
    expect(headers.get("authorization")).toBeNull();
    expect(JSON.parse(String(init?.body))).toEqual({
      message: "Explain this run",
      client_id: "client-1",
    });
  });
});
