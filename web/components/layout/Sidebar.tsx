"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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
  showHistoryButton?: boolean;
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
  showHistoryButton = true,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const classNames = ["sidebar"];
  if (collapsed) classNames.push("sidebar--collapsed");
  if (mobileOpen) classNames.push("sidebar--open");
  const navItems = [
    {
      href: "/overview",
      label: "Overview",
      shortLabel: "O",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M4 4h7v7H4V4zm9 0h7v4h-7V4zM4 13h7v7H4v-7zm9 6v-9h7v9h-7z"
            fill="currentColor"
          />
        </svg>
      ),
    },
    {
      href: "/",
      label: "Current chat",
      shortLabel: "C",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-4 3v-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"
            fill="currentColor"
          />
        </svg>
      ),
    },
    {
      href: "/simulation",
      label: "Simulation",
      shortLabel: "S",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M8 3h8l1 2h4v2H3V5h4l1-2zm1 7h2v7H9v-7zm4 0h2v7h-2v-7z"
            fill="currentColor"
          />
        </svg>
      ),
    },
    {
      href: "/evidence",
      label: "Evidence",
      shortLabel: "E",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M10 4a6 6 0 1 0 3.9 10.5l4.3 4.3 1.4-1.4-4.3-4.3A6 6 0 0 0 10 4z"
            fill="currentColor"
          />
        </svg>
      ),
    },
    {
      href: "/alignment",
      label: "Alignment",
      shortLabel: "A",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 3l2.1 4.3 4.7.7-3.4 3.3.8 4.7L12 13.8 7.8 16l.8-4.7L5.2 8l4.7-.7L12 3z"
            fill="currentColor"
          />
        </svg>
      ),
    },
  ];

  const historyIcon = (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 5a7 7 0 1 1-6.5 9.6H3l3.5-3.5L10 14H7.7A5 5 0 1 0 12 7V5zm-1 4h2v5h-4v-2h2V9z"
        fill="currentColor"
      />
    </svg>
  );

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
          className={`sidebar__item ${pathname === "/" ? "sidebar__item--active" : ""}`}
          onClick={() => {
            onNewConversation();
            if (mobileOpen) onMobileClose();
          }}
          title={collapsed ? "New chat" : undefined}
        >
          <span className="sidebar__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M11 4h2v6h6v2h-6v6h-2v-6H5v-2h6V4z" fill="currentColor" />
            </svg>
          </span>
          {!collapsed && <span className="sidebar__label">New chat</span>}
        </button>

        <div className="sidebar__nav-scroll">
          <div className="sidebar__nav-section">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`sidebar__item ${
                  pathname === item.href ? "sidebar__item--active" : ""
                }`}
                onClick={() => {
                  if (mobileOpen) onMobileClose();
                }}
                title={collapsed ? item.label : undefined}
              >
                <span className="sidebar__icon" aria-hidden="true">
                  {item.icon}
                </span>
                {!collapsed && <span className="sidebar__label">{item.label}</span>}
              </Link>
            ))}
          </div>
          {showHistoryButton && (
            <div className="sidebar__nav-section sidebar__nav-section--meta">
              <div className="sidebar__divider" aria-hidden="true" />
              <button
                type="button"
                className="sidebar__item sidebar__item--meta"
                onClick={() => {
                  onOpenHistory();
                  if (mobileOpen) onMobileClose();
                }}
                title={collapsed ? "History" : undefined}
              >
                <span className="sidebar__icon" aria-hidden="true">
                  {historyIcon}
                </span>
                {!collapsed && <span className="sidebar__label">History</span>}
              </button>
            </div>
          )}
        </div>
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
