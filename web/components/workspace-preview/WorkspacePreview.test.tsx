import React from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { WorkspacePreview } from "./WorkspacePreview";
import {
  advanceSampleStep,
  commitSampleDecision,
  sampleConversation,
  scenes,
} from "./model";

function viewport(mobile = false) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      matches: mobile,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}
beforeEach(() => viewport());
afterEach(() => vi.unstubAllGlobals());

describe("sample workspace interaction boundaries", () => {
  it("separates creation, nine individual confirmations and nine results without API calls", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    render(<WorkspacePreview initialScene="plan" />);
    await user.click(
      screen.getByRole("button", { name: "Confirm and create run" }),
    );
    await user.click(screen.getByText("Preview states"));
    for (let finished = 0; finished < 9; finished++) {
      expect(
        screen.getByText(`${finished} of 9 steps finished`),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Advance sample step" }),
      ).toBeNull();
      await user.click(screen.getByRole("button", { name: "Review approval" }));
      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveFocus();
      expect(screen.getByRole("main")).toHaveAttribute("inert");
      expect(
        screen.getByText(`${finished} of 9 steps finished`),
      ).toBeInTheDocument();
      await user.click(
        within(dialog).getByRole("button", { name: "Confirm approval" }),
      );
      expect(
        screen.getByText(`${finished} of 9 steps finished`),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Cancel run" })).toBeDisabled();
      expect(
        screen.queryByRole("button", { name: "Review approval" }),
      ).toBeNull();
      await user.click(
        screen.getByRole("button", { name: "Advance sample step" }),
      );
    }
    expect(
      screen.getByRole("heading", { name: /description is worth testing/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/customer impact has not been measured/i),
    ).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("keeps a started step pending across pause, then resumes with fresh approval required", async () => {
    const user = userEvent.setup();
    render(<WorkspacePreview initialScene="running" />);
    await user.click(screen.getByText("Preview states"));
    await user.click(
      screen.getByRole("button", { name: "Pause further work" }),
    );
    await user.click(screen.getByRole("button", { name: "Confirm pause" }));
    expect(
      screen.getByText(/started step may still finish/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel run" })).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "Advance sample step" }),
    );
    expect(screen.getByText("6 of 9 steps finished")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel run" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Review resume" }));
    await user.click(screen.getByRole("button", { name: "Confirm resume" }));
    expect(
      screen.getByRole("button", { name: "Review approval" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Advance sample step" }),
    ).toBeNull();
  });

  it("preserves each conversation's draft through navigation, theme and evidence inspection", async () => {
    const user = userEvent.setup();
    render(<WorkspacePreview initialScene="approval" />);
    const composer = screen.getByRole("textbox", { name: "Message Scout" });
    await user.type(composer, "Check the provider evidence first");
    await user.click(
      screen.getByRole("button", { name: "Supporting evidence" }),
    );
    await user.click(screen.getByRole("button", { name: "Close details" }));
    await user.click(screen.getByRole("button", { name: "Dark appearance" }));
    await user.click(
      screen.getByRole("button", { name: /Earlier trail shoe comparison/ }),
    );
    expect(composer).toHaveValue("");
    await user.type(composer, "Earlier work draft");
    await user.click(
      screen.getByRole("button", { name: /^Trail shoe comparison/ }),
    );
    expect(composer).toHaveValue("Check the provider evidence first");
    await user.click(screen.getByRole("button", { name: "Review approval" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Review approval" }),
    ).toHaveFocus();
    expect(screen.getByRole("main")).not.toHaveAttribute("inert");
  });

  it("isolates mobile navigation and inspectors from hidden/background controls", async () => {
    viewport(true);
    const user = userEvent.setup();
    render(<WorkspacePreview initialScene="approval" />);
    const navigation = screen.getByLabelText("Work conversations");
    expect(navigation).toHaveAttribute("inert");
    expect(navigation).toHaveAttribute("aria-hidden", "true");
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(
      screen.getByRole("dialog", { name: "Work conversations" }),
    ).toHaveFocus();
    expect(navigation).not.toHaveAttribute("inert");
    expect(screen.getByRole("main")).toHaveAttribute("inert");
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(screen.getByText("Preview states")).toHaveFocus();
    await user.keyboard("{Tab}");
    expect(
      screen.getByRole("button", { name: "Close navigation" }),
    ).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("button", { name: "Open navigation" }),
    ).toHaveFocus();
    await user.click(
      screen.getByRole("button", { name: "Supporting evidence" }),
    );
    const inspector = screen.getByRole("dialog", {
      name: "Comparison evidence",
    });
    expect(inspector).toHaveFocus();
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(screen.getByRole("button", { name: "Close details" })).toHaveFocus();
    await user.keyboard("{Tab}");
    expect(screen.getByRole("button", { name: "Close details" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("button", { name: "Supporting evidence" }),
    ).toHaveFocus();
  });

  it.each(scenes)(
    "renders the %s sample with no unsafe automatic work",
    (scene) => {
      render(<WorkspacePreview initialScene={scene} />);
      expect(screen.getByRole("main")).toBeInTheDocument();
      expect(
        screen.getByText("Design preview · sample data"),
      ).toBeInTheDocument();
      if (
        ["failed", "blocked", "partial", "cancelled", "outcome"].includes(scene)
      ) {
        expect(
          screen.queryByRole("button", { name: "Review approval" }),
        ).toBeNull();
        expect(
          screen.queryByRole("button", { name: /retry|resume/i }),
        ).toBeNull();
      }
    },
  );

  it("does not present planned inputs and candidate text as completed evidence", async () => {
    const user = userEvent.setup();
    render(<WorkspacePreview initialScene="plan" />);
    await user.click(
      screen.getByRole("button", { name: "Confirm and create run" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Supporting evidence" }),
    );
    const evidence = screen.getByRole("complementary", {
      name: "Comparison evidence",
    });
    expect(
      within(evidence).getByText("Comparison inputs not yet frozen"),
    ).toBeInTheDocument();
    expect(
      within(evidence).getByText("Candidate not yet prepared"),
    ).toBeInTheDocument();
    expect(within(evidence).queryByText(/Grip and comfort/)).toBeNull();
  });

  it("restores mobile focus to navigation after inspecting the assistant from its hidden sidebar", async () => {
    viewport(true);
    const user = userEvent.setup();
    render(<WorkspacePreview />);
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    await user.click(
      screen.getByRole("button", { name: /Scout, commerce assistant Scout/ }),
    );
    expect(screen.getByRole("dialog", { name: "Meet Scout" })).toHaveFocus();
    expect(
      screen.queryByRole("dialog", { name: "Work conversations" }),
    ).toBeNull();
    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("button", { name: "Open navigation" }),
    ).toHaveFocus();
  });

  it("opens an earlier comparison without replacing the new conversation's draft or state", async () => {
    const user = userEvent.setup();
    render(<WorkspacePreview />);
    await user.type(
      screen.getByRole("textbox", { name: "Message Scout" }),
      "My next comparison",
    );
    await user.click(
      screen.getByRole("button", { name: "Review an earlier comparison" }),
    );
    expect(
      screen.getByRole("button", {
        name: "Earlier trail shoe comparison Comparison finished",
      }),
    ).toHaveAttribute("aria-current", "page");
    await user.click(
      screen.getByRole("button", { name: "New conversation New conversation" }),
    );
    expect(screen.getByRole("textbox", { name: "Message Scout" })).toHaveValue(
      "My next comparison",
    );
    expect(
      screen.getByRole("heading", { name: "What would you like to improve?" }),
    ).toBeInTheDocument();
  });

  it.each(["failed", "cancelled", "outcome"] as const)(
    "refuses injected decisions and late results in %s",
    (scene) => {
      const current = sampleConversation("one", scene);
      for (const decision of [
        "approve",
        "resume",
        "cancel",
        "pause",
      ] as const) {
        const result = commitSampleDecision({ ...current, decision });
        expect(result.scene).toBe(scene);
        expect(result.completed).toBe(current.completed);
      }
      expect(advanceSampleStep({ ...current, activeStep: true }).scene).toBe(
        scene,
      );
    },
  );

  it("acknowledges a last result arriving during pause without inventing a tenth step", () => {
    const paused = {
      ...sampleConversation("one", "paused"),
      completed: 8,
      activeStep: true,
    };
    const settled = advanceSampleStep(paused);
    expect(settled.scene).toBe("paused");
    expect(settled.completed).toBe(9);
    expect(commitSampleDecision({ ...settled, decision: "resume" }).scene).toBe(
      "outcome",
    );
  });
});
