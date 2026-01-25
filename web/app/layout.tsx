import "./globals.css";
import type { ReactNode } from "react";
import { ClerkProvider } from "@clerk/nextjs";
import { TenantProvider } from "../components/tenant/TenantProvider";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <ClerkProvider
      appearance={{
        variables: {
          colorPrimary: "#10b981",
          colorBackground: "#0a0a0a",
          colorText: "#fafafa",
          colorTextSecondary: "#999999",
          colorInputBackground: "#171717",
          colorInputText: "#fafafa",
          colorAlphaShade: "#111111",
          colorAlpha: "rgba(16, 185, 129, 0.12)",
          colorDanger: "#ef4444",
          borderRadius: "8px",
          fontFamily: "var(--font-sans)",
        },
        elements: {
          card: "clerk-card",
          headerTitle: "clerk-title",
          headerSubtitle: "clerk-subtitle",
          formButtonPrimary: "clerk-button-primary",
          formFieldInput: "clerk-input",
          formFieldLabel: "clerk-label",
          socialButtonsBlockButton: "clerk-social",
          dividerText: "clerk-divider-text",
          userButtonPopoverCard: "clerk-popover",
          userButtonPopoverMain: "clerk-popover-main",
          userButtonPopoverFooter: "clerk-popover-footer",
          userButtonPopoverActionButton: "clerk-action",
          userButtonPopoverActionButtonText: "clerk-action-text",
          userButtonPopoverActionButtonIcon: "clerk-action-icon",
        },
      }}
    >
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
