import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "./page";

const pushMock = vi.fn();
const listAgentRunsMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({ user: { id: "user-1", firstName: "Dessi" } }),
}));

vi.mock("../components/layout/Sidebar", () => ({
  Sidebar: () => null,
}));

vi.mock("../components/layout/DetailHeader", () => ({
  DetailHeader: ({
    title,
    actions,
  }: {
    title: string;
    actions?: ReactNode;
  }) => (
    <header>
      <h1>{title}</h1>
      {actions}
    </header>
  ),
}));

vi.mock("../lib/api", () => ({
  listAgentRuns: (...args: unknown[]) => listAgentRunsMock(...args),
}));

describe("HomePage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    listAgentRunsMock.mockReset();
    listAgentRunsMock.mockResolvedValue({ runs: [] });
  });

  it("renders the control-plane landing and navigates to primary surfaces", async () => {
    const user = userEvent.setup();
    render(<HomePage />);

    expect(screen.getByText(/Operator briefing/i)).toBeInTheDocument();
    expect(screen.getByText(/Welcome back, Dessi/i)).toBeInTheDocument();
    expect(screen.getByText(/Operator path/i)).toBeInTheDocument();
    expect(screen.getByText(/When to leave the loop/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/No recent runs found/i))[0]).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Open runs/i }));
    expect(pushMock).toHaveBeenNthCalledWith(1, "/runs");

    await user.click(screen.getAllByText("Open lab")[0]);
    expect(pushMock).toHaveBeenNthCalledWith(2, "/lab");
  });

  it("recommends inbox when recent runs need failure triage", async () => {
    const user = userEvent.setup();
    listAgentRunsMock.mockResolvedValue({
      runs: [
        {
          id: "run-failed-1",
          client_id: "client-1",
          status: "failed",
          state: "validation_failed",
          requires_approval: true,
        },
        {
          id: "run-active-1",
          client_id: "client-1",
          status: "running",
          state: "executing",
          requires_approval: false,
        },
      ],
    });

    render(<HomePage />);

    expect(
      (await screen.findAllByText(/1 recent run needs failure triage/i))[0],
    ).toBeInTheDocument();
    expect(screen.getByText(/Needs attention:\s*1/i)).toBeInTheDocument();
    expect(screen.getByText(/Active runs:\s*1/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Review inbox/i }));

    expect(pushMock).toHaveBeenCalledWith("/inbox");
  });
});
