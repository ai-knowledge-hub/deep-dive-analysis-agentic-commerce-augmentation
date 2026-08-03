import { describe, expect, it } from "vitest";

import { buildCommandOutcome } from "./operatorChatLogic";

describe("operatorChatLogic", () => {
  it("uses linked-work wording for generic action results", () => {
    const outcome = buildCommandOutcome("step", {
      command: {
        id: "command-1",
        run_id: "run-1",
        sequence: 1,
        event_type: "operator_command_step",
        status: "executed",
      },
      run: {
        id: "run-1",
        client_id: "client-1",
        status: "running",
      },
      action: {
        id: "action-1",
        agent_run_id: "run-1",
        sequence: 1,
        status: "executed",
        capability_name: "recommend_next_action",
        outputs: {
          recommendation: "Review next safe action",
        },
      },
    });

    expect(outcome).toContain("Inspect the action results for linked work and decision details.");
    expect(outcome).not.toContain("output payload");
    expect(outcome).not.toContain("generated artifacts");
  });
});
