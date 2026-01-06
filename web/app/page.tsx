"use client";

import Link from "next/link";

export default function HomePage() {
  return (
    <section className="space-y-6">
      <h1 className="text-3xl font-semibold">Agentic Commerce</h1>
      <p>
        This workspace showcases the empowerment-first shopping assistant. Head to the chat
        experience to see values clarification, reasoning, and empowerment telemetry in action.
      </p>
      <Link
        href="/chat"
        className="inline-flex items-center rounded-md bg-emerald-500 px-4 py-2 font-semibold text-black hover:bg-emerald-400"
      >
        Launch Chat
      </Link>
    </section>
  );
}
