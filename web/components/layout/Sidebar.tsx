"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { useState } from "react";
import {
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";
import { isMockAuthEnabled } from "../../lib/auth";
import { useTenant } from "../tenant/TenantProvider";

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
  const [showTenantPanel, setShowTenantPanel] = useState(false);
  const pathname = usePathname();
  const isAdvancedLabRoute = [
    "/alignment",
    "/evidence",
    "/simulation",
    "/experiments",
    "/validation",
    "/overview",
  ].includes(pathname);
  const [advancedLabOpen, setAdvancedLabOpen] = useState(isAdvancedLabRoute);
  const mockAuth = isMockAuthEnabled();
  const {
    clients,
    clientId,
    brandId,
    productId,
    isAdminMode,
    setClientId,
    setBrandId,
    setProductId,
  } = useTenant();
  const selectedClient = clients.find((client) => client.id === clientId);
  const brands = selectedClient?.brands ?? [];
  const selectedBrand = brands.find((brand) => brand.id === brandId) ?? null;
  const products = selectedBrand?.products ?? [];
  const classNames = ["sidebar"];
  if (collapsed) classNames.push("sidebar--collapsed");
  if (mobileOpen) classNames.push("sidebar--open");
  const primaryItems = [
    {
      href: "/inbox",
      label: "Inbox",
      shortLabel: "I",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zm2 3v2h12V8H6zm0 5v2h7v-2H6z"
            fill="currentColor"
          />
        </svg>
      ),
    },
    {
      href: "/runs",
      label: "Runs",
      shortLabel: "R",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect
            x="4.5"
            y="6.5"
            width="15"
            height="12"
            rx="3"
            ry="3"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.3"
          />
          <line
            x1="12"
            y1="6.5"
            x2="12"
            y2="3.8"
            stroke="currentColor"
            strokeWidth="2.3"
            strokeLinecap="round"
          />
          <circle cx="12" cy="2.6" r="1.25" fill="currentColor" />
          <line
            x1="4.5"
            y1="11.5"
            x2="3"
            y2="11.5"
            stroke="currentColor"
            strokeWidth="2.3"
            strokeLinecap="round"
          />
          <line
            x1="19.5"
            y1="11.5"
            x2="21"
            y2="11.5"
            stroke="currentColor"
            strokeWidth="2.3"
            strokeLinecap="round"
          />
          <circle cx="9.1" cy="11.2" r="1.3" fill="currentColor" />
          <circle cx="14.9" cy="11.2" r="1.3" fill="currentColor" />
          <path
            d="M8.8 14.8c.9.9 2 1.3 3.2 1.3s2.3-.5 3.2-1.3"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      ),
    },
    {
      href: "/interventions",
      label: "Interventions",
      shortLabel: "IN",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 3l8 4v5c0 5.1-3.4 8.6-8 10-4.6-1.4-8-4.9-8-10V7l8-4zm-1 6v5h2V9h-2zm0 7v2h2v-2h-2z"
            fill="currentColor"
          />
        </svg>
      ),
    },
    {
      href: "/learnings",
      label: "Insights",
      shortLabel: "L",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 4l7 4v8l-7 4-7-4V8l7-4zm0 3.2L8 9.4v5.2l4 2.2 4-2.2V9.4L12 7.2z"
            fill="currentColor"
          />
        </svg>
      ),
    },
  ];
  const labItem = {
    href: "/lab",
    label: "Lab",
    shortLabel: "L",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M5 4h14a2 2 0 0 1 2 2v2H3V6a2 2 0 0 1 2-2zm-2 6h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8zm6 2v4h2v-4H9zm4 0v4h2v-4h-2z"
          fill="currentColor"
        />
      </svg>
    ),
  };
  const advancedLabItems = [
    {
      href: "/alignment",
      label: "Alignment",
      shortLabel: "A",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 4a6 6 0 1 1-6 6 6 6 0 0 1 6-6zm0 3a3 3 0 1 0 3 3 3 3 0 0 0-3-3z"
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
      href: "/simulation",
      label: "Simulation",
      shortLabel: "S",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M5 4h14a2 2 0 0 1 2 2v2H3V6a2 2 0 0 1 2-2zm-2 6h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8zm6 2v4h2v-4H9zm4 0v4h2v-4h-2z"
            fill="currentColor"
          />
        </svg>
      ),
    },
    {
      href: "/experiments",
      label: "Experiments",
      shortLabel: "X",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M9 3h6v2h-1v4.3l4.8 7.7A2 2 0 0 1 17.1 20H6.9a2 2 0 0 1-1.7-3L10 9.3V5H9V3zm2 8.1-4 6.4h10l-4-6.4V5h-2v6.1z"
            fill="currentColor"
          />
        </svg>
      ),
    },
    {
      href: "/validation",
      label: "Validation",
      shortLabel: "V",
      icon: (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M9 12l2 2 4-4 1.4 1.4-5.4 5.4-3.4-3.4L9 12zm3-10a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"
            fill="currentColor"
          />
        </svg>
      ),
    },
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
  ];
  const adminItems = isAdminMode
    ? [
        {
          href: "/admin",
          label: "Admin",
          shortLabel: "AD",
          icon: (
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M12 4l7 3v5c0 4.4-3 7.9-7 9-4-1.1-7-4.6-7-9V7l7-3zm0 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm0 8c-2.2 0-4 1.1-4 2.5V20h8v-1.5c0-1.4-1.8-2.5-4-2.5z"
                fill="currentColor"
              />
            </svg>
          ),
        },
      ]
    : [];

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
        {!collapsed && (
          <div className="sidebar__brand">
            {isAdminMode ? (
              <button
                type="button"
                className={`sidebar__item sidebar__item--meta sidebar__tenant-trigger ${
                  showTenantPanel ? "is-active" : ""
                }`}
                onClick={() => setShowTenantPanel((prev) => !prev)}
              >
                <span className="sidebar__label">
                  {selectedClient?.name ?? clientId}
                </span>
                <span className="sidebar__caret">▾</span>
              </button>
            ) : (
              <span>Intentionality</span>
            )}
          </div>
        )}
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
      {isAdminMode && !collapsed && (
        <>
          <button
            type="button"
            className={`tenant-overlay ${showTenantPanel ? "is-visible" : ""}`}
            onClick={() => setShowTenantPanel(false)}
            aria-label="Close tenant panel"
          />
          <div
            className={`sidebar__tenant-panel ${
              showTenantPanel ? "is-open" : ""
            }`}
          >
          <label className="sidebar__tenant-label" htmlFor="tenant-client">
            Client
          </label>
          <select
            id="tenant-client"
            className="sidebar__tenant-select"
            value={clientId}
            onChange={(event) => {
              setClientId(event.target.value);
              setShowTenantPanel(false);
            }}
          >
            {clients.map((client) => (
              <option key={client.id} value={client.id}>
                {client.name}
              </option>
            ))}
          </select>
          <label className="sidebar__tenant-label" htmlFor="tenant-brand">
            Brand
          </label>
          <select
            id="tenant-brand"
            className="sidebar__tenant-select"
            value={brandId ?? ""}
            onChange={(event) => {
              setBrandId(event.target.value || null);
              setShowTenantPanel(false);
            }}
          >
            <option value="">None</option>
            {brands.map((brand) => (
              <option key={brand.id} value={brand.id}>
                {brand.name}
              </option>
            ))}
          </select>
          <label className="sidebar__tenant-label" htmlFor="tenant-product">
            Product
          </label>
          <select
            id="tenant-product"
            className="sidebar__tenant-select"
            value={productId ?? ""}
            onChange={(event) => {
              setProductId(event.target.value || null);
              setShowTenantPanel(false);
            }}
            disabled={!selectedBrand}
          >
            <option value="">None</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name}
              </option>
            ))}
          </select>
        </div>
        </>
      )}

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
            {!collapsed && (
              <div className="sidebar__section-label">Control Plane</div>
            )}
            {primaryItems.map((item) => (
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
          <div className="sidebar__nav-section">
            <div className="sidebar__divider" aria-hidden="true" />
            {!collapsed && (
              <div className="sidebar__section-label">Lab</div>
            )}
            <Link
              href={labItem.href}
              className={`sidebar__item ${
                pathname === labItem.href ? "sidebar__item--active" : ""
              }`}
              onClick={() => {
                if (mobileOpen) onMobileClose();
              }}
              title={collapsed ? labItem.label : undefined}
            >
              <span className="sidebar__icon" aria-hidden="true">
                {labItem.icon}
              </span>
              {!collapsed && <span className="sidebar__label">{labItem.label}</span>}
            </Link>
            {!collapsed ? (
              <button
                type="button"
                className={`sidebar__item sidebar__item--meta sidebar__advanced-toggle ${
                  isAdvancedLabRoute ? "sidebar__item--active" : ""
                }`}
                aria-expanded={advancedLabOpen}
                onClick={() => setAdvancedLabOpen((open) => !open)}
              >
                <span className="sidebar__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path
                      d={
                        advancedLabOpen
                          ? "M7 10l5 5 5-5H7z"
                          : "M10 7l5 5-5 5V7z"
                      }
                      fill="currentColor"
                    />
                  </svg>
                </span>
                <span className="sidebar__label">Advanced lab</span>
              </button>
            ) : null}
            {advancedLabOpen && !collapsed ? (
              <div className="sidebar__advanced-list">
                {advancedLabItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`sidebar__item sidebar__item--advanced ${
                      pathname === item.href ? "sidebar__item--active" : ""
                    }`}
                    onClick={() => {
                      if (mobileOpen) onMobileClose();
                    }}
                  >
                    <span className="sidebar__icon" aria-hidden="true">
                      {item.icon}
                    </span>
                    <span className="sidebar__label">{item.label}</span>
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
          {adminItems.length ? (
            <div className="sidebar__nav-section">
              <div className="sidebar__divider" aria-hidden="true" />
              {!collapsed && (
                <div className="sidebar__section-label">Admin</div>
              )}
              {adminItems.map((item) => (
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
                  {!collapsed && (
                    <span className="sidebar__label">{item.label}</span>
                  )}
                </Link>
              ))}
            </div>
          ) : null}
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
            {mockAuth ? (
              <span className="sidebar__auth-button">Mock auth active</span>
            ) : (
              <>
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
              </>
            )}
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
