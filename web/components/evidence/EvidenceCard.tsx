/**
 * Evidence Card Component
 *
 * Displays a single evidence product with confidence scoring,
 * before/after optimization, and metadata.
 */

import React from "react";

interface EvidenceProduct {
  id: string;
  name: string;
  description: string;
  source: string;
  url?: string | null;
  price?: number | null;
  confidence: number;
  metadata?: Record<string, unknown>;
}

interface EvidenceCardProps {
  product: EvidenceProduct;
  optimizedDescription?: string | null;
  showOptimization?: boolean;
  index?: number;
  whySummary?: string;
  highlightSignals?: string[];
}

export function EvidenceCard({
  product,
  optimizedDescription,
  showOptimization = false,
  index,
  whySummary,
  highlightSignals = [],
}: EvidenceCardProps) {
  const alignmentScore =
    typeof product.metadata?.alignment_score === "number"
      ? product.metadata.alignment_score
      : null;
  const getScoreColor = (score: number): string => {
    if (score >= 0.7) return "#1cc886"; // green - high
    if (score >= 0.5) return "rgba(255, 255, 255, 0.7)"; // neutral - medium
    return "rgba(255, 255, 255, 0.45)"; // neutral - low
  };

  const getScoreLabel = (score: number): string => {
    if (score >= 0.7) return "High";
    if (score >= 0.5) return "Medium";
    return "Low";
  };

  const displayScore = alignmentScore ?? product.confidence ?? 0;
  const scoreColor = getScoreColor(displayScore);
  const scoreLabel = getScoreLabel(displayScore);
  const badgeLabel = alignmentScore !== null ? "ALIGN" : scoreLabel;
  const scorePercentage = Math.round(displayScore * 100);

  return (
    <div className="evidence-card">
      <div className="evidence-card__header">
        <div className="evidence-card__title">
          {index !== undefined && (
            <span className="evidence-card__rank">#{index + 1}</span>
          )}
          <h5>{product.name}</h5>
        </div>
        <div
          className="evidence-card__confidence"
          style={{ borderColor: scoreColor }}
        >
          <span
            className="confidence-value"
            style={{ color: scoreColor }}
          >
            {scorePercentage}%
          </span>
          <span className="confidence-label">{badgeLabel}</span>
        </div>
      </div>

      <div className="evidence-card__body">
        {/* Original Description */}
        <div className="evidence-section">
          <h6>Current Description</h6>
          <p className="description-text">{product.description}</p>
        </div>

        {/* Optimized Description (if available) */}
        {showOptimization && optimizedDescription && (
          <div className="evidence-section evidence-section--optimized">
            <h6>Optimized Description</h6>
            <p className="description-text description-text--optimized">
              {optimizedDescription}
            </p>
            <div className="optimization-badge">
              Intent-optimized
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="evidence-metadata">
          {whySummary && (
            <div className="metadata-row metadata-row--stacked">
              <span className="metadata-label">Why they win</span>
              <span className="metadata-value">{whySummary}</span>
            </div>
          )}
          {highlightSignals.length > 0 && (
            <div className="metadata-row metadata-row--stacked">
              <span className="metadata-label">Top signals</span>
              <div className="metadata-chips">
                {highlightSignals.slice(0, 3).map((signal) => (
                  <span key={signal} className="metadata-chip">
                    {signal}
                  </span>
                ))}
              </div>
            </div>
          )}
          {alignmentScore !== null && (
            <div className="metadata-row">
              <span className="metadata-label">Alignment:</span>
              <span className="metadata-value">
                {Math.round(alignmentScore * 100)}%
              </span>
            </div>
          )}
          <div className="metadata-row">
            <span className="metadata-label">Source:</span>
            <span className="metadata-value">{product.source}</span>
          </div>
          {product.price && (
            <div className="metadata-row">
              <span className="metadata-label">Price:</span>
              <span className="metadata-value">
                ${product.price.toFixed(2)}
              </span>
            </div>
          )}
          {product.url && (
            <div className="metadata-row">
              <a
                href={product.url}
                target="_blank"
                rel="noopener noreferrer"
                className="metadata-link"
              >
                View product →
              </a>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .evidence-card {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 1.1rem;
          transition: all 0.2s;
          max-height: 320px;
          display: flex;
          flex-direction: column;
        }

        .evidence-card:hover {
          background: rgba(255, 255, 255, 0.05);
          border-color: rgba(28, 200, 134, 0.3);
          transform: translateY(-2px);
        }

        .evidence-card__header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 1rem;
          margin-bottom: 0.75rem;
          padding-bottom: 0.75rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .evidence-card__title {
          flex: 1;
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .evidence-card__rank {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          background: rgba(28, 200, 134, 0.08);
          border: 1px solid rgba(28, 200, 134, 0.2);
          border-radius: 50%;
          font-size: 0.8rem;
          font-weight: 700;
          color: rgba(140, 255, 208, 0.9);
        }

        .evidence-card__title h5 {
          margin: 0;
          font-size: 0.95rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.95);
          line-height: 1.4;
          word-break: break-word;
        }

        .evidence-card__confidence {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          padding: 0.4rem 0.8rem;
          border: 1.5px solid;
          border-radius: 8px;
          background: rgba(0, 0, 0, 0.2);
          min-width: 72px;
          text-transform: uppercase;
        }

        .confidence-value {
          font-size: 1.1rem;
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

        .evidence-card__body {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          overflow-y: auto;
          padding-right: 0.25rem;
        }

        .evidence-section {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .evidence-section--optimized {
          position: relative;
          padding: 1rem;
          background: rgba(28, 200, 134, 0.04);
          border: 1px solid rgba(28, 200, 134, 0.18);
          border-radius: 6px;
        }

        .evidence-section h6 {
          margin: 0;
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
        }

        .description-text {
          margin: 0;
          font-size: 0.875rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.85);
          word-break: break-word;
          overflow-wrap: anywhere;
          display: -webkit-box;
          -webkit-line-clamp: 6;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        .description-text--optimized {
          color: rgba(255, 255, 255, 0.95);
          -webkit-line-clamp: 8;
        }

        .optimization-badge {
          position: absolute;
          top: -10px;
          right: 1rem;
          padding: 0.25rem 0.75rem;
          background: rgba(28, 200, 134, 0.2);
          color: rgba(140, 255, 208, 0.95);
          font-size: 0.65rem;
          font-weight: 700;
          text-transform: uppercase;
          border-radius: 12px;
          letter-spacing: 0.5px;
        }

        .evidence-metadata {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          margin-top: 0.5rem;
          padding-top: 1rem;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .metadata-row {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.8125rem;
        }

        .metadata-row--stacked {
          flex-direction: column;
          align-items: flex-start;
          gap: 0.35rem;
        }

        .metadata-label {
          font-weight: 600;
          color: rgba(255, 255, 255, 0.5);
        }

        .metadata-value {
          color: rgba(255, 255, 255, 0.8);
        }

        .metadata-link {
          color: rgba(140, 255, 208, 0.9);
          text-decoration: none;
          font-weight: 600;
          transition: color 0.2s;
        }

        .metadata-link:hover {
          color: rgba(140, 255, 208, 1);
          text-decoration: underline;
        }

        .metadata-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 0.35rem;
        }

        .metadata-chip {
          padding: 0.2rem 0.5rem;
          border-radius: 999px;
          background: rgba(28, 200, 134, 0.1);
          border: 1px solid rgba(28, 200, 134, 0.25);
          color: rgba(140, 255, 208, 0.9);
          font-size: 0.65rem;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .evidence-card__body::-webkit-scrollbar {
          width: 6px;
        }

        .evidence-card__body::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.12);
          border-radius: 6px;
        }

        .evidence-card__body::-webkit-scrollbar-track {
          background: transparent;
        }
      `}</style>
    </div>
  );
}
