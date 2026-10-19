import React from "react";
import type { OperatorConversationResponse } from "../../lib/operatorConversationTypes";

export function OperatorAnswerDetails({ response }: { response: OperatorConversationResponse }) {
  return (
        <div className="operator-chat__artifacts" aria-label="Verified answer details">
          <div className="panel__notice panel__notice--info">
            Evidence view {response.snapshot.digest.slice(0, 12)} · {response.freshness.state}
            {" · "}Data {response.freshness.data_state}
            {" · "}Cursor {response.freshness.snapshot_cursor?.slice(0, 12) ?? "no events"}
          </div>
          <p className="panel__muted">Answer recorded: {new Date(response.snapshot.fetched_at).toLocaleString()}. Freshness reflects answer time; progress refresh preserves this evidence.</p>
          {response.warnings.map((warning) => (
            <div key={warning.code} className="panel__notice panel__notice--warning">
              {warning.message}
            </div>
          ))}
          {response.recommendation ? (
            <div className="panel__notice panel__notice--info">
              <strong>Recommendation:</strong> {response.recommendation.text}
            </div>
          ) : null}
          <details className="panel__details">
            <summary className="panel__details-summary">
              Verified facts ({response.verified_facts.length})
            </summary>
            <ul className="operator-chat__fact-list">
              {response.verified_facts.map((fact) => (
                <li key={fact.id}>
                  <span>{fact.text}</span>
                  <small>
                    {fact.category} · {fact.trust ?? "authoritative_projection"} · {fact.provenance.record_type}{" "}
                    <a href={fact.source}>Source</a>
                  </small>
                </li>
              ))}
            </ul>
          </details>
          {response.evidence.length ? (
            <details className="panel__details">
              <summary className="panel__details-summary">
                Evidence records ({response.evidence.length})
              </summary>
              <ul className="operator-chat__fact-list">
                {response.evidence.map((item, index) => {
                  const evidenceId = String(
                    item.record.evidence_id ?? item.record.id ?? `record-${index + 1}`,
                  );
                  const sourceType = String(item.record.source_type ?? item.kind);
                  return (
                    <li key={`${item.kind}-${evidenceId}-${index}`}>
                      <span>{evidenceId}</span>
                      <small>
                        {sourceType} · <a href={item.href}>Open evidence</a>
                      </small>
                    </li>
                  );
                })}
              </ul>
            </details>
          ) : null}
          <div className="panel__actions">
            {response.navigation.map((link) => (
              <a key={link.href} className="button button--ghost button--sm" href={link.href}>
                {link.label}
              </a>
            ))}
          </div>
        </div>
  );
}
