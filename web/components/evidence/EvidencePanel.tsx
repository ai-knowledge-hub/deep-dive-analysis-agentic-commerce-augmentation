/**
 * Evidence Panel Component
 *
 * Main panel for displaying evidence analysis, optimization, and verification.
 * Enhanced with beautiful visualizations and demo data support.
 */

"use client";

import React, { useState } from "react";
import type {
  EvidenceAnalyzeResponse,
  RepresentationOptimizeResponse,
  RecommendationVerifyResponse,
} from "../../lib/types";
import { EvidenceCard } from "./EvidenceCard";
import { OptimizationComparison } from "./OptimizationComparison";
import { VerificationMetrics } from "./VerificationMetrics";

type Props = {
  analysis?: EvidenceAnalyzeResponse | null;
  optimization?: RepresentationOptimizeResponse | null;
  verification?: RecommendationVerifyResponse | null;
  onLoadDemo?: () => void | Promise<void>;
};

export function EvidencePanel({
  analysis,
  optimization,
  verification,
  onLoadDemo,
}: Props) {
  const [activeTab, setActiveTab] = useState<
    "evidence" | "optimization" | "verification"
  >("evidence");

  const hasData = Boolean(analysis);
  const hasOptimization = Boolean(optimization);
  const hasVerification = Boolean(verification);

  if (!hasData) {
    return (
      <div className="panel__card">
        <div className="panel__header">
          <h3>Evidence Discovery</h3>
        </div>
        <div className="empty-state">
          <div className="empty-state__icon">🔍</div>
          <h4 className="empty-state__title">No Evidence Data</h4>
          <p className="empty-state__description">
            Run a query to see evidence-based product discovery results, or load demo data to explore the flow.
          </p>
          {onLoadDemo && (
            <button
              type="button"
              className="empty-state__action"
              onClick={onLoadDemo}
            >
              Load Demo Data
            </button>
          )}
        </div>

        <style jsx>{`
          .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 4rem 2rem;
            text-align: center;
          }

          .empty-state__icon {
            font-size: 4rem;
            margin-bottom: 1rem;
            opacity: 0.5;
          }

          .empty-state__title {
            margin: 0 0 0.75rem 0;
            font-size: 1.25rem;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.9);
          }

          .empty-state__description {
            margin: 0 0 1.5rem 0;
            font-size: 0.9375rem;
            color: rgba(255, 255, 255, 0.6);
            max-width: 500px;
            line-height: 1.6;
          }

          .empty-state__action {
            padding: 0.75rem 1.5rem;
            background: #1cc886;
            border: none;
            border-radius: 6px;
            color: white;
            font-size: 0.9375rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
          }

          .empty-state__action:hover {
            background: #2dd89c;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(28, 200, 134, 0.3);
          }
        `}</style>
      </div>
    );
  }

  const evidenceProducts = analysis?.evidence_products ?? [];
  const optimizedItems = optimization?.optimized ?? [];

  // Create a map of optimized descriptions by product ID
  const optimizationMap = new Map(
    optimizedItems.map((item) => [item.id, item.after])
  );

  return (
    <div className="evidence-panel">
      {/* Header with Tabs */}
      <div className="evidence-panel__header">
        <div className="header-title">
          <h3>Evidence Discovery</h3>
          <span className="header-badge">{evidenceProducts.length} products</span>
        </div>
        <div className="header-tabs">
          <button
            type="button"
            className={`tab ${activeTab === "evidence" ? "tab--active" : ""}`}
            onClick={() => setActiveTab("evidence")}
          >
            Evidence
            {evidenceProducts.length > 0 && (
              <span className="tab-badge">{evidenceProducts.length}</span>
            )}
          </button>
          <button
            type="button"
            className={`tab ${activeTab === "optimization" ? "tab--active" : ""}`}
            onClick={() => setActiveTab("optimization")}
            disabled={!hasOptimization}
          >
            Optimization
            {optimizedItems.length > 0 && (
              <span className="tab-badge">{optimizedItems.length}</span>
            )}
          </button>
          <button
            type="button"
            className={`tab ${activeTab === "verification" ? "tab--active" : ""}`}
            onClick={() => setActiveTab("verification")}
            disabled={!hasVerification}
          >
            Verification
            {hasVerification && <span className="tab-indicator">✓</span>}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="evidence-panel__content">
        {/* Evidence Tab */}
        {activeTab === "evidence" && (
          <div className="evidence-grid">
            {evidenceProducts.map((product, index) => (
              <EvidenceCard
                key={product.id}
                product={product}
                optimizedDescription={optimizationMap.get(product.id)}
                showOptimization={hasOptimization}
                index={index}
              />
            ))}
          </div>
        )}

        {/* Optimization Tab */}
        {activeTab === "optimization" && (
          <div className="optimization-content">
            {hasOptimization ? (
              <OptimizationComparison optimized={optimizedItems} />
            ) : (
              <div className="tab-empty">
                <p>No optimization data available.</p>
                <p className="tab-empty__hint">
                  Run representation optimization to see before/after comparisons.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Verification Tab */}
        {activeTab === "verification" && (
          <div className="verification-content">
            {hasVerification ? (
              <VerificationMetrics
                predicted={verification.predicted ?? []}
                actual={verification.actual ?? []}
                lift={verification.lift ?? 0}
              />
            ) : (
              <div className="tab-empty">
                <p>No verification data available.</p>
                <p className="tab-empty__hint">
                  Run recommendation verification to measure discoverability lift.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      <style jsx>{`
        .evidence-panel {
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          overflow: hidden;
        }

        .evidence-panel__header {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          padding: 1.5rem;
          background: rgba(255, 255, 255, 0.03);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .header-title {
          display: flex;
          align-items: center;
          gap: 1rem;
        }

        .header-title h3 {
          margin: 0;
          font-size: 1.25rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.95);
        }

        .header-badge {
          padding: 0.25rem 0.75rem;
          background: rgba(28, 200, 134, 0.15);
          border: 1px solid rgba(28, 200, 134, 0.3);
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: 700;
          color: #1cc886;
        }

        .header-tabs {
          display: flex;
          gap: 0.5rem;
          overflow-x: auto;
        }

        .tab {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.75rem 1.25rem;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 6px;
          color: rgba(255, 255, 255, 0.7);
          font-size: 0.875rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          white-space: nowrap;
        }

        .tab:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.05);
          color: rgba(255, 255, 255, 0.9);
          border-color: rgba(255, 255, 255, 0.2);
        }

        .tab--active {
          background: #1cc886;
          border-color: #1cc886;
          color: white;
        }

        .tab:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .tab-badge {
          padding: 0.125rem 0.5rem;
          background: rgba(255, 255, 255, 0.2);
          border-radius: 8px;
          font-size: 0.75rem;
          font-weight: 700;
        }

        .tab--active .tab-badge {
          background: rgba(255, 255, 255, 0.25);
        }

        .tab-indicator {
          font-size: 0.875rem;
        }

        .evidence-panel__content {
          padding: 2rem;
        }

        .evidence-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
          gap: 1.5rem;
        }

        @media (max-width: 768px) {
          .evidence-grid {
            grid-template-columns: 1fr;
          }
        }

        .optimization-content,
        .verification-content {
          max-width: 1200px;
          margin: 0 auto;
        }

        .tab-empty {
          padding: 4rem 2rem;
          text-align: center;
          color: rgba(255, 255, 255, 0.6);
        }

        .tab-empty p {
          margin: 0 0 0.5rem 0;
        }

        .tab-empty__hint {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.4);
        }
      `}</style>
    </div>
  );
}
