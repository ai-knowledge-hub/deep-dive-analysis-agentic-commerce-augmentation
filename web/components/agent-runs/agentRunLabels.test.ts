import { describe, expect, it } from "vitest";

import { formatAgentRunLabel } from "./agentRunLabels";

describe("formatAgentRunLabel", () => {
  it("uses readable objective context before timestamps", () => {
    expect(
      formatAgentRunLabel({
        id: "run-1",
        client_id: "client-a",
        experiment_id: "exp-a",
        objective: { objective: "checkout_confidence" },
      }),
    ).toBe("Experiment run · checkout confidence");
  });

  it("uses created date when objective context is unavailable", () => {
    expect(
      formatAgentRunLabel({
        id: "run-2",
        client_id: "client-a",
        status: "planned",
        created_at: "2026-01-02T00:00:00Z",
      }),
    ).toMatch(/Standalone run · started 1\/2\/2026/);
  });

  it("does not expose raw experiment or run ids as a fallback", () => {
    expect(
      formatAgentRunLabel({
        id: "run-raw",
        client_id: "client-a",
        experiment_id: "exp-raw",
      }),
    ).toBe("Experiment run");
  });
});
