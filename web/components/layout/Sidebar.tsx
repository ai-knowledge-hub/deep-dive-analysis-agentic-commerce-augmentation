"use client";

import { useState } from "react";

type Props = {
  mobileOpen: boolean;
  onMobileClose: () => void;
};

export function Sidebar({ mobileOpen, onMobileClose }: Props) {
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
        {!collapsed && <span className="sidebar__brand">Empowerment</span>}
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
          onClick={mobileOpen ? onMobileClose : undefined}
        >
          {!collapsed && <span className="sidebar__label">New conversation</span>}
          {collapsed && <span className="sidebar__icon">+</span>}
        </button>
      </nav>

      {!collapsed && (
        <div className="sidebar__footer">
          <div className="sidebar__info">
            <span className="sidebar__info-label">World B Commerce</span>
            <span className="sidebar__info-text">Values-first shopping</span>
          </div>
        </div>
      )}
    </aside>
  );
}
