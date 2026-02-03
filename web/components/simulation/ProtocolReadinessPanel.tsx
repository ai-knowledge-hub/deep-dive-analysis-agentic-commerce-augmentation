"use client";

type ReadinessIssue = {
  protocol?: string;
  field?: string;
  severity?: string;
  message?: string;
};

type Props = {
  title?: string;
  issues?: ReadinessIssue[];
  actionLabel?: string;
  onAction?: () => void;
  emptyMessage?: string;
};

export function ProtocolReadinessPanel({
  title = "Protocol readiness",
  issues = [],
  actionLabel = "Open simulation",
  onAction,
  emptyMessage = "Run a simulation to see ACP/UCP readiness.",
}: Props) {
  const isDemoMode =
    typeof process !== "undefined" &&
    process.env.NEXT_PUBLIC_PROTOCOL_MODE === "demo";

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h3>{title}</h3>
        <div className="panel__meta">
          {isDemoMode ? <span className="panel__badge">Demo</span> : null}
          {onAction ? (
            <button type="button" className="panel__action" onClick={onAction}>
              {actionLabel}
            </button>
          ) : null}
          {issues.length > 0 && <span className="panel__badge">{issues.length}</span>}
        </div>
      </div>

      {issues.length === 0 ? (
        <p className="panel__empty">{emptyMessage}</p>
      ) : (
        <div className="products">
          {issues.map((issue, idx) => (
            <div key={`${issue.field ?? "issue"}-${idx}`} className="product">
              <div className="product__header">
                <span className="product__name">{issue.field ?? "Readiness check"}</span>
                <div className="product__meta">
                  {issue.protocol ? (
                    <span className="product__flag">{issue.protocol.toUpperCase()}</span>
                  ) : null}
                  {issue.severity ? (
                    <span className="product__confidence">{issue.severity}</span>
                  ) : null}
                </div>
              </div>
              <p className="product__reasoning">{issue.message ?? "Missing protocol detail."}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
