/**
 * Belief Card Component
 *
 * Displays a single brand belief with confidence, recommendation, and evidence.
 */

import React, { useState } from "react";
import { buildExperimentHref, buildSimulationHref } from "../../lib/routes";

interface BeliefCardProps {
  belief: {
    id: string;
    brand_id: string;
    product_id?: string;
    hypothesis: Record<string, any>;
    evidence: Record<string, any>;
    recommendation: string;
    confidence: number;
    metadata: Record<string, any>;
    created_at: string;
  };
  onUseBelief?: (belief: BeliefCardProps["belief"]) => void;
}

export function BeliefCard({ belief, onUseBelief }: BeliefCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.7) return "#1cc886"; // green - high
    if (confidence >= 0.5) return "#fbbf24"; // yellow - medium
    return "#fb923c"; // orange - low
  };

  const getConfidenceLabel = (confidence: number): string => {
    if (confidence >= 0.7) return "High Confidence";
    if (confidence >= 0.5) return "Medium Confidence";
    return "Low Confidence";
  };

  const confidenceColor = getConfidenceColor(belief.confidence);
  const confidenceLabel = getConfidenceLabel(belief.confidence);
  const confidencePercentage = Math.round(belief.confidence * 100);

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return date.toLocaleDateString();
  };

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return "—";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
    try {
      const json = JSON.stringify(value);
      if (json.length > 140) {
        return `${json.slice(0, 140)}…`;
      }
      return json;
    } catch {
      return String(value);
    }
  };

  return (
    <div className="belief-card">
      <div className="belief-card__header">
        <div className="belief-card__title">
          <h5>{belief.recommendation}</h5>
          <span className="belief-card__date">{formatDate(belief.created_at)}</span>
        </div>
        {typeof belief.metadata?.support === "boolean" ? (
          <span
            className={`belief-card__support ${
              belief.metadata.support ? "is-supported" : "is-rejected"
            }`}
          >
            {belief.metadata.support ? "Supported" : "Not supported"}
          </span>
        ) : null}
        <div
          className="belief-card__confidence"
          style={{ borderColor: confidenceColor }}
        >
          <span className="confidence-value" style={{ color: confidenceColor }}>
            {confidencePercentage}%
          </span>
          <span className="confidence-label">{confidenceLabel}</span>
        </div>
      </div>

      <div className="belief-card__body">
        <div className="belief-section belief-section--summary">
          <h6>Summary</h6>
          <p className="belief-summary">
            {belief.metadata?.summary
              ? String(belief.metadata.summary)
              : "No summary yet."}
          </p>
          {onUseBelief ? (
            <button
              type="button"
              className="belief-cta"
              onClick={() => onUseBelief(belief)}
            >
              Use as hypothesis
            </button>
          ) : null}
        </div>

        <div className="belief-structure">
          {/* Hypothesis */}
          {belief.hypothesis && Object.keys(belief.hypothesis).length > 0 && (
            <div className="belief-section">
              <h6>Hypothesis</h6>
              <div className="belief-content">
                {Object.entries(belief.hypothesis).map(([key, value]) => (
                  <div key={key} className="belief-item">
                    <span className="item-key">{key}:</span>
                    <span className="item-value">{formatValue(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evidence Summary */}
          {belief.evidence && Object.keys(belief.evidence).length > 0 && (
            <div className="belief-section">
              <h6>Evidence</h6>
              <div className="belief-content">
                {Object.entries(belief.evidence)
                  .slice(0, isExpanded ? undefined : 2)
                  .map(([key, value]) => (
                    <div key={key} className="belief-item">
                      <span className="item-key">{key}:</span>
                      <span className="item-value">{formatValue(value)}</span>
                    </div>
                  ))}
                {Object.keys(belief.evidence).length > 2 && (
                  <button
                    type="button"
                    className="expand-btn"
                    onClick={() => setIsExpanded(!isExpanded)}
                  >
                    {isExpanded
                      ? "Show less"
                      : `Show ${
                          Object.keys(belief.evidence).length - 2
                        } more`}
                  </button>
                )}
                <div className="belief-links">
                  {belief.evidence?.experiment_id && (
                    <a
                      className="belief-link"
                      href={buildExperimentHref(belief.evidence.experiment_id)}
                    >
                      Open experiment
                    </a>
                  )}
                  {Array.isArray(belief.evidence?.runs) &&
                    belief.evidence.runs[0]?.run_id && (
                      <a
                        className="belief-link"
                        href={buildSimulationHref(belief.evidence.runs[0].run_id)}
                      >
                        Open linked run
                      </a>
                    )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Metadata */}
        {belief.metadata && Object.keys(belief.metadata).length > 0 && (
          <div className="belief-section">
            <h6>Context</h6>
            <div className="belief-metadata">
              {belief.metadata.variant_type && (
                <span className="metadata-tag">{belief.metadata.variant_type}</span>
              )}
              {belief.metadata.experiment_count && (
                <span className="metadata-tag">
                  {belief.metadata.experiment_count} experiments
                </span>
              )}
              {belief.product_id && (
                <span className="metadata-tag">Product-specific</span>
              )}
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .belief-card {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 1.5rem;
          transition: all 0.2s;
        }

        .belief-card:hover {
          background: rgba(255, 255, 255, 0.05);
          border-color: rgba(28, 200, 134, 0.3);
        }

        .belief-card__header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 1rem;
          margin-bottom: 1rem;
        }

        .belief-card__title {
          flex: 1;
        }

        .belief-card__title h5 {
          margin: 0 0 0.5rem 0;
          font-size: 1rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.95);
          line-height: 1.4;
        }

        .belief-card__date {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .belief-card__confidence {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          padding: 0.5rem 1rem;
          border: 2px solid;
          border-radius: 8px;
          background: rgba(0, 0, 0, 0.2);
        }

        .belief-card__support {
          align-self: flex-start;
          padding: 0.2rem 0.6rem;
          border-radius: 999px;
          font-size: 0.65rem;
          text-transform: uppercase;
          font-weight: 600;
          letter-spacing: 0.02em;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: rgba(255, 255, 255, 0.06);
          color: rgba(255, 255, 255, 0.7);
        }

        .belief-card__support.is-supported {
          border-color: rgba(28, 200, 134, 0.5);
          background: rgba(28, 200, 134, 0.12);
          color: #1cc886;
        }

        .belief-card__support.is-rejected {
          border-color: rgba(239, 68, 68, 0.4);
          background: rgba(239, 68, 68, 0.12);
          color: #f87171;
        }

        .confidence-value {
          font-size: 1.25rem;
          font-weight: 700;
          line-height: 1;
        }

        .confidence-label {
          font-size: 0.65rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
          margin-top: 0.25rem;
        }

        .belief-summary {
          margin: 0;
          font-size: 0.9rem;
          color: rgba(255, 255, 255, 0.75);
          line-height: 1.4;
        }

        .belief-cta {
          margin-top: 0.75rem;
          background: rgba(28, 200, 134, 0.15);
          border: 1px solid rgba(28, 200, 134, 0.5);
          color: #1cc886;
          font-size: 0.7rem;
          padding: 0.35rem 0.75rem;
          border-radius: 999px;
          cursor: pointer;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          font-weight: 600;
        }

        .belief-cta:hover {
          background: rgba(28, 200, 134, 0.25);
        }

        .belief-section--summary {
          padding: 0.75rem 1rem;
          border-radius: 8px;
          background: rgba(28, 200, 134, 0.06);
          border: 1px solid rgba(28, 200, 134, 0.2);
        }

        .belief-structure {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 1rem;
          margin-top: 1rem;
        }

        .belief-card__body {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .belief-section {
          padding-top: 1rem;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .belief-section:first-child {
          padding-top: 0;
          border-top: none;
        }

        .belief-section h6 {
          margin: 0 0 0.75rem 0;
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
        }

        .belief-content {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .belief-links {
          display: flex;
          flex-wrap: wrap;
          gap: 0.75rem;
          margin-top: 0.5rem;
        }

        .belief-link {
          font-size: 0.75rem;
          color: #1cc886;
          text-decoration: none;
        }

        .belief-link:hover {
          text-decoration: underline;
        }

        .belief-item {
          display: flex;
          gap: 0.5rem;
          font-size: 0.875rem;
          line-height: 1.5;
        }

        .item-key {
          font-weight: 600;
          color: rgba(255, 255, 255, 0.7);
          text-transform: capitalize;
        }

        .item-value {
          color: rgba(255, 255, 255, 0.9);
        }

        .expand-btn {
          margin-top: 0.5rem;
          padding: 0.25rem 0.75rem;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          color: #1cc886;
          font-size: 0.75rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .expand-btn:hover {
          background: rgba(28, 200, 134, 0.1);
          border-color: #1cc886;
        }

        .belief-metadata {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
        }

        .metadata-tag {
          display: inline-block;
          padding: 0.25rem 0.75rem;
          background: rgba(59, 130, 246, 0.1);
          border: 1px solid rgba(59, 130, 246, 0.3);
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: 600;
          color: #3b82f6;
        }
      `}</style>
    </div>
  );
}
