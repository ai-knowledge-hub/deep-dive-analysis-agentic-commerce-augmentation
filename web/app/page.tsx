"use client";

import React, { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";

import { Sidebar } from "../components/layout/Sidebar";
import { ControlPlaneBriefing } from "../components/layout/ControlPlaneBriefing";
import { DetailHeader } from "../components/layout/DetailHeader";

type EntryCard = {
  title: string;
  summary: string;
  href: string;
  cta: string;
  badge?: string;
};

const PRIMARY_ENTRY_CARDS: EntryCard[] = [
  {
    title: "Inbox",
    summary: "Start with blocked, failed, and approval-needed execution items.",
    href: "/inbox",
    cta: "Open inbox",
    badge: "Triage",
  },
  {
    title: "Runs",
    summary: "Inspect active and recent runs with the operator chat beside execution state.",
    href: "/runs",
    cta: "Open runs",
    badge: "Primary",
  },
  {
    title: "Interventions",
    summary: "Approve, pause, reject, resume, and manually review high-signal execution paths.",
    href: "/interventions",
    cta: "Open interventions",
    badge: "Control",
  },
  {
    title: "Learnings",
    summary: "Review what changed recently and where the next operator attention should go.",
    href: "/learnings",
    cta: "Open learnings",
    badge: "Review",
  },
];

const SECONDARY_ENTRY_CARDS: EntryCard[] = [
  {
    title: "Open the lab",
    summary: "Use the full conversational workspace when you want to run the exploratory, human-led lab flow directly.",
    href: "/lab",
    cta: "Open lab",
  },
  {
    title: "Open overview",
    summary: "Keep the legacy cross-surface dashboard available while the control plane takes shape.",
    href: "/overview",
    cta: "Open overview",
  },
];

export default function HomePage() {
  const router = useRouter();
  const { user } = useUser();
  const [isSidebarOpen, setSidebarOpen] = useState(false);

  const greeting = useMemo(() => {
    const firstName = user?.firstName?.trim();
    return firstName ? `Welcome back, ${firstName}.` : "Welcome back.";
  }, [user?.firstName]);

  return (
    <div className="app">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/lab")}
        sessions={[]}
        activeSessionId={null}
        onSelectSession={() => {}}
        onDeleteSession={() => {}}
        onOpenHistory={() => {}}
        showHistoryButton={false}
      />

      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Control Plane"
            subtitle="The default entry for supervising autonomous execution, handling interventions, and reviewing what changed."
            onMenu={() => setSidebarOpen(true)}
            actions={
              <button
                type="button"
                className="button button--ghost"
                onClick={() => router.push("/lab")}
              >
                Open lab
              </button>
            }
          />

          <ControlPlaneBriefing
            label="Entry"
            title="Operator briefing"
            subtitle={`${greeting} This surface is now optimized for supervision first, with the lab available when you want to drive the workflow directly.`}
            summary="Start with Inbox if you need to triage attention quickly, or open Runs if you already know which execution context you want to inspect."
            metrics={[
              { label: "Primary views", value: 4 },
              { label: "Lab access", value: "Available" },
            ]}
          />

          <section className="agent-workspace inbox-workspace">
            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Primary control plane</h3>
                <span className="panel__badge panel__badge--warning">Default</span>
              </div>
              <div className="list">
                {PRIMARY_ENTRY_CARDS.map((item) => (
                  <div key={item.title} className="list__row">
                    <div className="list__title">{item.title}</div>
                    {item.badge ? (
                      <div className="list__meta">
                        <span className="panel__badge panel__badge--secondary">{item.badge}</span>
                      </div>
                    ) : null}
                    <div className="panel__muted">{item.summary}</div>
                    <div className="detail__actions">
                      <button
                        type="button"
                        className="button button--ghost button--sm"
                        onClick={() => router.push(item.href)}
                      >
                        {item.cta}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Suggested operator paths</h3>
                <span className="panel__badge panel__badge--secondary">Guided</span>
              </div>
              <div className="list">
                <div className="list__row">
                  <div className="list__title">If execution feels unstable</div>
                  <div className="panel__muted">
                    Start in `Inbox`, move into `Interventions`, then inspect the affected run in `Runs`.
                  </div>
                </div>
                <div className="list__row">
                  <div className="list__title">If execution is healthy but opaque</div>
                  <div className="panel__muted">
                    Start in `Runs`, use the operator chat for explanation, then finish in `Learnings` to understand what changed.
                  </div>
                </div>
                <div className="list__row">
                  <div className="list__title">If you want to drive the system directly</div>
                  <div className="panel__muted">
                    Open the `Lab` and use the chat-led workspace for exploratory, human-guided operation.
                  </div>
                </div>
              </div>
            </section>

            <section className="panel__card panel__card--secondary">
              <div className="panel__header">
                <h3>Secondary surfaces</h3>
                <span className="panel__badge panel__badge--secondary">Bridge</span>
              </div>
              <div className="list">
                {SECONDARY_ENTRY_CARDS.map((item) => (
                  <div key={item.title} className="list__row">
                    <div className="list__title">{item.title}</div>
                    <div className="panel__muted">{item.summary}</div>
                    <div className="detail__actions">
                      <button
                        type="button"
                        className="button button--ghost button--sm"
                        onClick={() => router.push(item.href)}
                      >
                        {item.cta}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </section>
        </div>
      </main>
    </div>
  );
}
