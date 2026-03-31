import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React, { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "./page";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({ user: { firstName: "Dessi" } }),
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

describe("HomePage", () => {
  beforeEach(() => {
    pushMock.mockReset();
  });

  it("renders the control-plane landing and navigates to primary surfaces", async () => {
    const user = userEvent.setup();
    render(<HomePage />);

    expect(screen.getByText(/Operator briefing/i)).toBeInTheDocument();
    expect(screen.getByText(/Welcome back, Dessi/i)).toBeInTheDocument();
    expect(screen.getByText(/Primary control plane/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Open runs/i }));
    expect(pushMock).toHaveBeenNthCalledWith(1, "/runs");

    await user.click(screen.getAllByText("Open lab")[0]);
    expect(pushMock).toHaveBeenNthCalledWith(2, "/lab");
  });
});
