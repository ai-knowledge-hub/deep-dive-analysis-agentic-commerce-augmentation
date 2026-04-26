"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { useAppUser } from "../../lib/auth";
import { Sidebar } from "./Sidebar";
import { DetailHeader } from "./DetailHeader";

type Props = {
  title: string;
  subtitle: string;
  badge?: string;
  summary: string;
  nextItems: string[];
};

export function ControlPlanePlaceholder({
  title,
  subtitle,
  badge,
  summary,
  nextItems,
}: Props) {
  const router = useRouter();
  const { user } = useAppUser();

  return (
    <div className="app">
      <Sidebar
        mobileOpen={false}
        onMobileClose={() => {}}
        onNewConversation={() => router.push("/")}
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
            title={title}
            subtitle={subtitle}
            onMenu={() => {}}
            onBack={() => router.push("/runs")}
            actions={
              badge ? (
                <span className="panel__badge panel__badge--secondary">{badge}</span>
              ) : undefined
            }
          />

          <section className="panel__card panel__card--secondary panel__card--full-row">
            <div className="panel__header">
              <div className="panel__meta panel__meta--stack">
                <h3>{title}</h3>
                <div className="panel__subtitle">
                  First control-plane slice for the chat-led operator console.
                </div>
              </div>
            </div>
            <div className="panel__notice panel__notice--info">{summary}</div>
            <ul className="panel__list panel__list--compact">
              {nextItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <div className="panel__actions">
              <button
                type="button"
                className="button button--ghost"
                onClick={() => router.push("/runs")}
              >
                Open runs
              </button>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => router.push("/")}
              >
                Open lab
              </button>
            </div>
            {!user ? (
              <p className="panel__muted">
                Sign in to populate this control-plane route with tenant data.
              </p>
            ) : null}
          </section>
        </div>
      </main>
    </div>
  );
}
