"use client";

import React, { forwardRef, type ReactNode } from "react";

type Props = {
  labMode: "lab" | "manual";
  collapsed: boolean;
  hasProduct: boolean;
  protocolSnapshotVersion: number | null | undefined;
  hypothesesReady: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  children: ReactNode;
};

export const ExperimentSetupFlowPanel = forwardRef<HTMLElement, Props>(
  function ExperimentSetupFlowPanel(
    {
      labMode,
      collapsed,
      hasProduct,
      protocolSnapshotVersion,
      hypothesesReady,
      onCollapsedChange,
      children,
    },
    ref,
  ) {
  return (
    <section
      ref={ref}
      className="panel__card panel__card--primary"
      tabIndex={-1}
      aria-label="Experiment setup"
    >
      <div className="panel__header">
        <h3>{labMode === "lab" ? "Lab Setup Flow" : "Experiment Setup Flow"}</h3>
        <div className="panel__meta">
          <button
            type="button"
            className="panel__action panel__action--ghost"
            onClick={() => onCollapsedChange(!collapsed)}
          >
            {collapsed ? "Expand setup" : "Collapse setup"}
          </button>
        </div>
      </div>
      <div className="panel__meta">
        <span className="panel__badge panel__badge--secondary">
          Evidence protocol: {protocolSnapshotVersion && protocolSnapshotVersion > 0
            ? `v${protocolSnapshotVersion}`
            : "pending"}
        </span>
        <span className="panel__badge panel__badge--secondary">
          Test ideas: {hypothesesReady ? "ready" : "pending"}
        </span>
      </div>
      <p className="panel__subheading">Setup phase · Step 1</p>
      <p className="panel__muted">
        {labMode === "lab"
          ? "Prepare battery and queries first. Experiment context is initialized once and then stays in the background."
          : "Prepare battery and queries first. Experiment context auto-initializes when Step 4 starts."}
      </p>
      {collapsed ? (
        <p className="panel__empty">
          Setup is collapsed. Expand to edit battery and query controls.
        </p>
      ) : hasProduct ? (
        children
      ) : (
        <p className="panel__empty">Select a product to create a battery.</p>
      )}
    </section>
  );
  },
);
