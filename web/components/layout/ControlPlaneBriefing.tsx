import React from "react";

type Metric = {
  label: string;
  value: string | number;
  tone?: "default" | "warning";
};

type Props = {
  label: string;
  title: string;
  subtitle: string;
  summary: string;
  metrics?: Metric[];
  status?: string | null;
  error?: string | null;
};

export function ControlPlaneBriefing({
  label,
  title,
  subtitle,
  summary,
  metrics = [],
  status,
  error,
}: Props) {
  return (
    <section className="panel__card panel__card--secondary panel__card--full-row">
      <div className="panel__header">
        <div className="panel__meta panel__meta--stack">
          <div className="list__meta">
            <span className="panel__badge panel__badge--secondary">{label}</span>
          </div>
          <h3>{title}</h3>
          <div className="panel__subtitle">{subtitle}</div>
        </div>
      </div>
      {metrics.length > 0 ? (
        <div className="agent-ops-summary">
          {metrics.map((item) => (
            <span
              key={`${item.label}-${item.value}`}
              className={`panel__badge ${
                item.tone === "warning"
                  ? "panel__badge--warning"
                  : "panel__badge--secondary"
              }`}
            >
              {item.label}: {item.value}
            </span>
          ))}
        </div>
      ) : null}
      <div className="panel__notice panel__notice--info">{summary}</div>
      {status ? <div className="panel__notice panel__notice--info">{status}</div> : null}
      {error ? <div className="panel__notice panel__notice--error">{error}</div> : null}
    </section>
  );
}
