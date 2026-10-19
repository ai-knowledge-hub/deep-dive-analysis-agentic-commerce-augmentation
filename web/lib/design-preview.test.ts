import { afterEach, describe, expect, it, vi } from "vitest";
import WorkspaceDesignPage from "../app/design/workspace/page";

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NOT_FOUND");
  },
}));
afterEach(() => vi.unstubAllEnvs());
describe("server-only preview admission", () => {
  it.each([
    ["production", undefined],
    ["production", "false"],
    ["production", "TRUE"],
    [undefined, undefined],
    [undefined, "false"],
  ])("hides the route for mode=%s flag=%s", (mode, flag) => {
    vi.stubEnv("NODE_ENV", mode);
    vi.stubEnv("WORKSPACE_DESIGN_PREVIEW", flag);
    expect(() =>
      WorkspaceDesignPage({ searchParams: { scene: "outcome" } }),
    ).toThrow("NOT_FOUND");
  });
  it.each(["development", "test", "production"])(
    "allows explicit preview in %s",
    (mode) => {
      vi.stubEnv("NODE_ENV", mode);
      vi.stubEnv(
        "WORKSPACE_DESIGN_PREVIEW",
        mode === "production" ? "true" : undefined,
      );
      expect(
        WorkspaceDesignPage({ searchParams: { scene: "approval" } }).props
          .initialScene,
      ).toBe("approval");
      expect(
        WorkspaceDesignPage({ searchParams: { scene: "bad-scene" } }).props
          .initialScene,
      ).toBe("start");
    },
  );
});
