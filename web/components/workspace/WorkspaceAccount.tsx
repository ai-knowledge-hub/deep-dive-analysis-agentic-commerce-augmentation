"use client";
import React from "react";
import { SignedIn, SignedOut, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { isMockAuthEnabled } from "../../lib/auth";
import { useTenant } from "../tenant/TenantProvider";

export function WorkspaceAccount() {
  const tenant = useTenant();
  const client = tenant.clients.find((item) => item.id === tenant.clientId);
  const brands = client?.brands ?? [];
  const brand = brands.find((item) => item.id === tenant.brandId);
  return <div className="workspace-account">
    <small>{tenant.clientName || tenant.clientId || "Select a tenant"}</small>
    {tenant.isAdminMode && <a href="/admin">Admin</a>}
    {tenant.isAdminMode && <details><summary>Workspace scope</summary>
      <label>Client<select value={tenant.clientId} onChange={(e) => tenant.setClientId(e.target.value)}>
        {tenant.clients.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
      <label>Brand<select value={tenant.brandId ?? ""} onChange={(e) => tenant.setBrandId(e.target.value || null)}>
        <option value="">None</option>{brands.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
      <label>Product<select value={tenant.productId ?? ""} disabled={!brand} onChange={(e) => tenant.setProductId(e.target.value || null)}>
        <option value="">None</option>{brand?.products.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
    </details>}
    {isMockAuthEnabled() ? <small>Mock auth active</small> : <div className="workspace-auth">
      <SignedOut><SignInButton /><SignUpButton /></SignedOut><SignedIn><UserButton /></SignedIn>
    </div>}
  </div>;
}
