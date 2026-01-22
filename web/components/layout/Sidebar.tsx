"use client";

import { useState } from "react";
import {
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";

type SessionSummary = {
  id: string;
  preview?: string;
  last_turn_at?: string;
};

type Props = {
  mobileOpen: boolean;
  onMobileClose: () => void;
  onNewConversation: () => void;
  sessions: SessionSummary[];
  activeSessionId?: string | null;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onOpenHistory: () => void;
};

export function Sidebar({
  mobileOpen,
  onMobileClose,
  onNewConversation,
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  onOpenHistory,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const classNames = ["sidebar"];
  if (collapsed) classNames.push("sidebar--collapsed");
  if (mobileOpen) classNames.push("sidebar--open");

  return (
    <aside className={classNames.join(" ")}>
      <div className="sidebar__header">
        <button
          type="button"
          className="sidebar__toggle"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? ">" : "<"}
        </button>
        {!collapsed && <span className="sidebar__brand">Intentionality</span>}
        {mobileOpen && (
          <button
            type="button"
            className="sidebar__mobile-close"
            onClick={onMobileClose}
            aria-label="Close menu"
          >
            ×
          </button>
        )}
      </div>

      <nav className="sidebar__nav">
        <button
          type="button"
          className="sidebar__item sidebar__item--active"
          onClick={() => {
            onNewConversation();
            if (mobileOpen) onMobileClose();
          }}
        >
          {!collapsed && <span className="sidebar__label">New conversation</span>}
          {collapsed && <span className="sidebar__icon">+</span>}
        </button>

        {!collapsed && (
          <div className="sidebar__nav-scroll">
            <button
              type="button"
              className="sidebar__item"
              onClick={() => {
                onOpenHistory();
                if (mobileOpen) onMobileClose();
              }}
            >
              <span className="sidebar__label">History</span>
            </button>
          </div>
        )}
      </nav>

      {!collapsed && (
        <div className="sidebar__footer">
          <div className="sidebar__auth">
            <SignedOut>
              <SignInButton />
              <SignUpButton>
                <button type="button" className="sidebar__auth-button">
                  Sign up
                </button>
              </SignUpButton>
            </SignedOut>
            <SignedIn>
              <UserButton />
            </SignedIn>
          </div>
          <div className="sidebar__info">
            <span className="sidebar__info-label">Discovery Commerce</span>
            <span className="sidebar__info-text">Goal-aligned shopping</span>
          </div>
        </div>
      )}
    </aside>
  );
}
