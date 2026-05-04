import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { Sidebar } from "./Sidebar";

let pathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

vi.mock("@clerk/nextjs", () => ({
  SignedIn: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SignedOut: () => null,
  SignInButton: () => null,
  SignUpButton: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  UserButton: () => <span>User</span>,
}));

vi.mock("../../lib/auth", () => ({
  isMockAuthEnabled: () => true,
}));

vi.mock("../tenant/TenantProvider", () => ({
  useTenant: () => ({
    clients: [{ id: "acme", name: "Acme" }],
    clientId: "acme",
    brandId: null,
    productId: null,
    isAdminMode: false,
    setClientId: () => {},
    setBrandId: () => {},
    setProductId: () => {},
  }),
}));

function renderSidebar() {
  return render(
    <Sidebar
      mobileOpen={false}
      onMobileClose={vi.fn()}
      onNewConversation={vi.fn()}
      sessions={[]}
      activeSessionId={null}
      onSelectSession={vi.fn()}
      onDeleteSession={vi.fn()}
      onOpenHistory={vi.fn()}
    />,
  );
}

describe("Sidebar", () => {
  it("keeps lab secondary by hiding advanced lab tools behind a disclosure", async () => {
    pathname = "/";
    const user = userEvent.setup();
    renderSidebar();

    expect(screen.getByRole("link", { name: /Lab/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Simulation/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Advanced lab/i }));

    expect(screen.getByRole("link", { name: /Simulation/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Experiments/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Validation/i })).toBeInTheDocument();
  });

  it("opens advanced lab tools when the active route is inside the advanced lab", () => {
    pathname = "/validation";
    renderSidebar();

    expect(screen.getByRole("button", { name: /Advanced lab/i })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByRole("link", { name: /Validation/i })).toBeInTheDocument();
  });
});
