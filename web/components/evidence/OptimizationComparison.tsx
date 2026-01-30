/**
 * Optimization Comparison Component
 *
 * Displays before/after comparison of product descriptions
 * showing the intent-optimization improvements.
 */

import React, { useState } from "react";

interface OptimizedItem {
  id: string;
  name: string;
  before: string;
  after: string;
}

interface OptimizationComparisonProps {
  optimized: OptimizedItem[];
}

export function OptimizationComparison({
  optimized,
}: OptimizationComparisonProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const calculateImprovement = (before: string, after: string): number => {
    // Simple heuristic: outcome-focused language is typically longer
    // and includes more descriptive, benefit-oriented words
    const beforeWords = before.split(/\s+/).length;
    const afterWords = after.split(/\s+/).length;
    const wordIncrease = ((afterWords - beforeWords) / beforeWords) * 100;

    // Check for intent-signaling words
    const intentWords = [
      "combat", "reduce", "enjoy", "support", "built for",
      "helps", "keeps", "enables", "allows", "ensures"
    ];
    const afterIntentCount = intentWords.filter(word =>
      after.toLowerCase().includes(word)
    ).length;
    const beforeIntentCount = intentWords.filter(word =>
      before.toLowerCase().includes(word)
    ).length;

    const intentIncrease = afterIntentCount - beforeIntentCount;

    // Combine metrics for an improvement score (0-100)
    return Math.min(100, Math.max(0, (intentIncrease * 20) + Math.min(wordIncrease, 30)));
  };

  if (optimized.length === 0) {
    return (
      <div className="optimization-empty">
        <p>No optimizations available yet.</p>
      </div>
    );
  }

  return (
    <div className="optimization-comparison">
      <div className="comparison-header">
        <h4>Representation Optimizations</h4>
        <p className="comparison-subtitle">
          Before and after intent-optimization showing improved discoverability
        </p>
      </div>

      <div className="comparison-list">
        {optimized.map((item, index) => {
          const isExpanded = expandedIds.has(item.id);
          const improvement = calculateImprovement(item.before, item.after);

          return (
            <div key={item.id} className="comparison-item">
              <div className="comparison-item__header">
                <div className="comparison-item__title">
                  <span className="item-rank">#{index + 1}</span>
                  <span className="item-name">{item.name}</span>
                </div>
                <div className="comparison-item__score">
                  <span className="score-label">Improvement</span>
                  <span className="score-value">+{improvement.toFixed(0)}%</span>
                </div>
              </div>

              <div className="comparison-item__body">
                {/* Before */}
                <div className="comparison-side comparison-side--before">
                  <div className="side-label">
                    <span className="label-icon">⚠️</span>
                    <span className="label-text">Before (Spec-focused)</span>
                  </div>
                  <p className="side-text">
                    {isExpanded
                      ? item.before
                      : item.before.length > 120
                      ? `${item.before.slice(0, 120)}...`
                      : item.before}
                  </p>
                </div>

                {/* Arrow */}
                <div className="comparison-arrow">→</div>

                {/* After */}
                <div className="comparison-side comparison-side--after">
                  <div className="side-label">
                    <span className="label-icon">✨</span>
                    <span className="label-text">After (Intent-optimized)</span>
                  </div>
                  <p className="side-text">
                    {isExpanded
                      ? item.after
                      : item.after.length > 120
                      ? `${item.after.slice(0, 120)}...`
                      : item.after}
                  </p>
                </div>
              </div>

              {(item.before.length > 120 || item.after.length > 120) && (
                <button
                  type="button"
                  className="expand-btn"
                  onClick={() => toggleExpanded(item.id)}
                >
                  {isExpanded ? "Show less" : "Show more"}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <style jsx>{`
        .optimization-comparison {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }

        .optimization-empty {
          padding: 3rem;
          text-align: center;
          color: rgba(255, 255, 255, 0.5);
        }

        .comparison-header {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .comparison-header h4 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.95);
        }

        .comparison-subtitle {
          margin: 0;
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .comparison-list {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }

        .comparison-item {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 1.5rem;
          transition: all 0.2s;
        }

        .comparison-item:hover {
          background: rgba(255, 255, 255, 0.05);
          border-color: rgba(28, 200, 134, 0.3);
        }

        .comparison-item__header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1.5rem;
          padding-bottom: 1rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .comparison-item__title {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .item-rank {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          background: rgba(59, 130, 246, 0.1);
          border: 1px solid rgba(59, 130, 246, 0.3);
          border-radius: 50%;
          font-size: 0.75rem;
          font-weight: 700;
          color: #3b82f6;
        }

        .item-name {
          font-size: 1rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.9);
        }

        .comparison-item__score {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 0.25rem;
        }

        .score-label {
          font-size: 0.65rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.5);
        }

        .score-value {
          font-size: 1.25rem;
          font-weight: 700;
          color: #1cc886;
        }

        .comparison-item__body {
          display: grid;
          grid-template-columns: 1fr auto 1fr;
          gap: 1.5rem;
          align-items: start;
        }

        @media (max-width: 768px) {
          .comparison-item__body {
            grid-template-columns: 1fr;
          }

          .comparison-arrow {
            display: none;
          }
        }

        .comparison-side {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .comparison-side--before {
          background: rgba(251, 146, 60, 0.05);
          border: 1px solid rgba(251, 146, 60, 0.2);
          border-radius: 6px;
          padding: 1rem;
        }

        .comparison-side--after {
          background: rgba(28, 200, 134, 0.05);
          border: 1px solid rgba(28, 200, 134, 0.2);
          border-radius: 6px;
          padding: 1rem;
        }

        .side-label {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .label-icon {
          font-size: 0.875rem;
        }

        .label-text {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.7);
        }

        .side-text {
          margin: 0;
          font-size: 0.875rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.85);
        }

        .comparison-arrow {
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.5rem;
          color: #1cc886;
          padding-top: 2rem;
        }

        .expand-btn {
          margin-top: 1rem;
          padding: 0.5rem 1rem;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          color: #1cc886;
          font-size: 0.75rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          width: 100%;
        }

        .expand-btn:hover {
          background: rgba(28, 200, 134, 0.1);
          border-color: #1cc886;
        }
      `}</style>
    </div>
  );
}
