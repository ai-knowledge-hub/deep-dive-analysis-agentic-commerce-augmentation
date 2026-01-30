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
}

export function EvidenceCard({
  product,
  optimizedDescription,
  showOptimization = false,
  index,
}: EvidenceCardProps) {
  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.7) return "#1cc886"; // green - high
    if (confidence >= 0.5) return "#fbbf24"; // yellow - medium
    return "#fb923c"; // orange - low
  };

  const getConfidenceLabel = (confidence: number): string => {
    if (confidence >= 0.7) return "High";
    if (confidence >= 0.5) return "Medium";
    return "Low";
  };

  const confidenceColor = getConfidenceColor(product.confidence);
  const confidenceLabel = getConfidenceLabel(product.confidence);
  const confidencePercentage = Math.round(product.confidence * 100);

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
          style={{ borderColor: confidenceColor }}
        >
          <span
            className="confidence-value"
            style={{ color: confidenceColor }}
          >
            {confidencePercentage}%
          </span>
          <span className="confidence-label">{confidenceLabel}</span>
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
          padding: 1.5rem;
          transition: all 0.2s;
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
          margin-bottom: 1rem;
          padding-bottom: 1rem;
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
          width: 32px;
          height: 32px;
          background: rgba(28, 200, 134, 0.1);
          border: 1px solid rgba(28, 200, 134, 0.3);
          border-radius: 50%;
          font-size: 0.875rem;
          font-weight: 700;
          color: #1cc886;
        }

        .evidence-card__title h5 {
          margin: 0;
          font-size: 1rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.95);
          line-height: 1.4;
        }

        .evidence-card__confidence {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          padding: 0.5rem 1rem;
          border: 2px solid;
          border-radius: 8px;
          background: rgba(0, 0, 0, 0.2);
          min-width: 80px;
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

        .evidence-card__body {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .evidence-section {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .evidence-section--optimized {
          position: relative;
          padding: 1rem;
          background: rgba(28, 200, 134, 0.05);
          border: 1px solid rgba(28, 200, 134, 0.2);
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
        }

        .description-text--optimized {
          color: rgba(255, 255, 255, 0.95);
        }

        .optimization-badge {
          position: absolute;
          top: -10px;
          right: 1rem;
          padding: 0.25rem 0.75rem;
          background: #1cc886;
          color: white;
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

        .metadata-label {
          font-weight: 600;
          color: rgba(255, 255, 255, 0.5);
        }

        .metadata-value {
          color: rgba(255, 255, 255, 0.8);
        }

        .metadata-link {
          color: #1cc886;
          text-decoration: none;
          font-weight: 600;
          transition: color 0.2s;
        }

        .metadata-link:hover {
          color: #2dd89c;
          text-decoration: underline;
        }
      `}</style>
    </div>
  );
}
