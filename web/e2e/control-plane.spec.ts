import { expect, test } from "@playwright/test";

const routes = [
  { path: "/", heading: "Control Plane" },
  { path: "/inbox", heading: "Inbox" },
  { path: "/runs", heading: "Runs" },
  { path: "/interventions", heading: "Interventions" },
  { path: "/learnings", heading: "Learnings" },
  { path: "/validation", heading: "Validation" },
  { path: "/simulation", heading: "Simulation Sandbox" },
];

test.describe("mock-auth control plane", () => {
  for (const route of routes) {
    test(`${route.path} renders as an authenticated operator surface`, async ({ page }) => {
      await page.goto(route.path);

      await expect(page.getByRole("heading", { name: route.heading }).first()).toBeVisible();
      await expect(page.getByText("Mock auth active")).toBeVisible();
      await expect(page.getByText(/Sign in to/i)).toHaveCount(0);
    });
  }
});
