import "./globals.css";
import type { ReactNode } from "react";
import { ClerkProvider } from "@clerk/nextjs";

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
        <body>{children}</body>
      </html>
    </ClerkProvider>
  );
}
