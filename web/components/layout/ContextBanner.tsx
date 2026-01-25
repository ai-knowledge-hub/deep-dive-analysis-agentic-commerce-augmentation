"use client";

import { useTenant } from "../tenant/TenantProvider";

export function ContextBanner() {
  const { clientName, brandName, productName } = useTenant();
  const parts = [
    `Client: ${clientName}`,
    brandName ? `Brand: ${brandName}` : null,
    productName ? `Product: ${productName}` : null,
  ].filter(Boolean);

  return <div className="context-banner">{parts.join(" / ")}</div>;
}
