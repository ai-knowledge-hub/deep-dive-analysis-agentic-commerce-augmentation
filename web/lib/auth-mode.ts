export function isMockAuthEnabled(): boolean {
  const allowProductionMock =
    process.env.NEXT_PUBLIC_ALLOW_MOCK_AUTH_IN_PRODUCTION === "true";

  return (
    process.env.NEXT_PUBLIC_AUTH_MODE === "mock" &&
    (process.env.NODE_ENV !== "production" || allowProductionMock)
  );
}
