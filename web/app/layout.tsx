"use client";

import "./globals.css";
import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <title>Intentionality Commerce</title>
        <meta
          name="description"
          content="Intentionality optimization for AI commerce discovery"
        />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
