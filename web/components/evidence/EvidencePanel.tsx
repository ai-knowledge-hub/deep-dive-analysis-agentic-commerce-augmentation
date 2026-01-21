"use client";

import type {
  EvidenceAnalyzeResponse,
  RepresentationOptimizeResponse,
  RecommendationVerifyResponse,
} from "../../lib/types";

type Props = {
  analysis?: EvidenceAnalyzeResponse | null;
  optimization?: RepresentationOptimizeResponse | null;
  verification?: RecommendationVerifyResponse | null;
};

export function EvidencePanel({ analysis, optimization, verification }: Props) {
  if (!analysis) {
    return (
      <div className="panel__card">
        <div className="panel__header">
          <h3>Evidence Discovery</h3>
        </div>
        <p className="panel__empty">Run a query to see evidence-based results.</p>
      </div>
    );
  }

  return (
    <div className="panel__card evidence">
      <div className="panel__header">
        <h3>Evidence Discovery</h3>
        {analysis.evidence_products?.length ? (
          <span className="panel__badge">{analysis.evidence_products.length}</span>
        ) : null}
      </div>

      <div className="evidence__section">
        <div className="evidence__label">Evidence products</div>
        <div className="evidence__list">
          {(analysis.evidence_products ?? []).map((item) => (
            <div key={item.id} className="evidence__item">
              <div className="evidence__name">{item.name}</div>
              <div className="evidence__text">{item.description}</div>
              {item.url ? (
                <div className="evidence__meta">{item.url}</div>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      {optimization ? (
        <div className="evidence__section">
          <div className="evidence__label">Representation optimization</div>
          <div className="evidence__list">
            {(optimization.optimized ?? []).map((item) => (
              <div key={item.id} className="evidence__item">
                <div className="evidence__name">{item.name}</div>
                <div className="evidence__meta">Before</div>
                <div className="evidence__text">{item.before}</div>
                <div className="evidence__meta">After</div>
                <div className="evidence__text">{item.after}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {verification ? (
        <div className="evidence__section">
          <div className="evidence__label">Discoverability lift</div>
          <div className="evidence__lift">
            <div>Predicted: {verification.predicted?.length ?? 0}</div>
            <div>Actual: {verification.actual?.length ?? 0}</div>
            <div>Lift: {(verification.lift * 100).toFixed(0)}%</div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
