"use client";

import type { ReactNode } from "react";

type Props = {
  title: string;
  subtitle?: string;
  onMenu?: () => void;
  onBack?: () => void;
  backLabel?: string;
  actions?: ReactNode;
};

export function DetailHeader({
  title,
  subtitle,
  onMenu,
  onBack,
  backLabel,
  actions,
}: Props) {
  return (
    <div className="detail__header">
      <div className="detail__title">
        {onMenu ? (
          <button
            type="button"
            className="mobile-toggle"
            onClick={onMenu}
            aria-label="Open menu"
          >
            Menu
          </button>
        ) : null}
        <h2>{title}</h2>
        {subtitle ? <p className="detail__subhead">{subtitle}</p> : null}
      </div>
      {actions || onBack ? (
        <div className="detail__actions">
          {actions}
          {onBack ? (
            <button
              type="button"
              className="button button--ghost"
              onClick={onBack}
            >
              {backLabel ?? "Back to chat"}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
