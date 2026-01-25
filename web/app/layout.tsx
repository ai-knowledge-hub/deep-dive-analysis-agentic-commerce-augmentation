import "./globals.css";
import type { ReactNode } from "react";
import { ClerkProvider } from "@clerk/nextjs";
import { TenantProvider } from "../components/tenant/TenantProvider";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <head>
          <title>Intentionality Commerce</title>
          <meta
            name="description"
            content="Intentionality optimization for AI commerce discovery"
          />
        </head>
        <body>
          <TenantProvider>{children}</TenantProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
