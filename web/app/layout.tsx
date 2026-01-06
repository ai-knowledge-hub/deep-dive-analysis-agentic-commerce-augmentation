"use client";

import "./globals.css";
import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <title>Empowerment Commerce</title>
        <meta name="description" content="AI shopping that optimizes for empowerment, not addiction" />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
