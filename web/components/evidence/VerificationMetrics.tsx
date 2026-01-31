/**
 * Verification Metrics Component
 *
 * Displays discoverability lift metrics from before/after optimization,
 * showing predicted vs actual results.
 */

import React from "react";

interface VerificationMetricsProps {
  predicted: unknown[];
  actual: unknown[];
  lift: number;
}

export function VerificationMetrics({
  predicted,
  actual,
  lift,
}: VerificationMetricsProps) {
  const predictedCount = predicted?.length ?? 0;
  const actualCount = actual?.length ?? 0;
  const liftPercentage = Math.round(lift * 100);

  const getLiftColor = (liftValue: number): string => {
    if (liftValue >= 50) return "#1cc886"; // green - excellent
    if (liftValue >= 25) return "#fbbf24"; // yellow - good
    if (liftValue > 0) return "#fb923c"; // orange - modest
    return "#ef4444"; // red - negative
  };

  const getLiftLabel = (liftValue: number): string => {
    if (liftValue >= 50) return "Excellent";
    if (liftValue >= 25) return "Good";
    if (liftValue > 0) return "Modest";
    return "Needs work";
  };

  const liftColor = getLiftColor(liftPercentage);
  const liftLabel = getLiftLabel(liftPercentage);

  return (
    <div className="verification-metrics">
      <div className="metrics-header">
        <h4>Discoverability Verification</h4>
        <p className="metrics-subtitle">
          Measuring the improvement in AI agent discovery after optimization
        </p>
      </div>

      <div className="metrics-grid">
        {/* Predicted (Before) */}
        <div className="metric-card metric-card--before">
          <div className="metric-icon">📊</div>
          <div className="metric-content">
            <span className="metric-label">Before Optimization</span>
            <span className="metric-value">{predictedCount}</span>
            <span className="metric-sublabel">products discovered</span>
          </div>
        </div>

        {/* Actual (After) */}
        <div className="metric-card metric-card--after">
          <div className="metric-icon">🎯</div>
          <div className="metric-content">
            <span className="metric-label">After Optimization</span>
            <span className="metric-value">{actualCount}</span>
            <span className="metric-sublabel">products discovered</span>
          </div>
        </div>

        {/* Lift */}
        <div
          className="metric-card metric-card--lift"
          style={{ borderColor: liftColor }}
        >
          <div className="metric-icon">🚀</div>
          <div className="metric-content">
            <span className="metric-label">Discoverability Lift</span>
            <span className="metric-value" style={{ color: liftColor }}>
              {liftPercentage > 0 ? '+' : ''}{liftPercentage}%
            </span>
            <span className="metric-sublabel">{liftLabel} improvement</span>
          </div>
        </div>
      </div>

      {/* Visual Progress Bar */}
      <div className="lift-visualization">
        <div className="lift-bar-container">
          <div className="lift-bar-track">
            <div
              className="lift-bar-fill"
              style={{
                width: `${Math.min(100, Math.abs(liftPercentage))}%`,
                backgroundColor: liftColor,
              }}
            />
          </div>
          <div className="lift-bar-labels">
            <span>0%</span>
            <span>50%</span>
            <span>100%</span>
          </div>
        </div>
      </div>

      {/* Insight */}
      <div className="metrics-insight">
        <h5>What this means:</h5>
        <p>
          {liftPercentage > 0 ? (
            <>
              After intent-optimization, <strong>{actualCount - predictedCount} more products</strong>
              {" "}were successfully discovered by AI shopping agents, representing a
              {" "}<strong>{liftPercentage}% increase</strong> in discoverability.
              This demonstrates that outcome-focused language significantly improves
              your products&apos; visibility to AI-powered search.
            </>
          ) : liftPercentage === 0 ? (
            <>
              The optimization maintained the same level of discoverability.
              This suggests the original descriptions were already well-optimized
              for intent-based discovery, or additional optimization strategies
              may be needed.
            </>
          ) : (
            <>
              The optimization resulted in <strong>{Math.abs(liftPercentage)}% fewer discoveries</strong>.
              This indicates that the optimization strategy may need refinement.
              Consider testing different approaches to intent-focused language.
            </>
          )}
        </p>
      </div>

      <style jsx>{`
        .verification-metrics {
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }

        .metrics-header {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .metrics-header h4 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.95);
        }

        .metrics-subtitle {
          margin: 0;
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1rem;
        }

        .metric-card {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 1.5rem;
          display: flex;
          align-items: center;
          gap: 1rem;
          transition: all 0.2s;
        }

        .metric-card:hover {
          background: rgba(255, 255, 255, 0.05);
          transform: translateY(-2px);
        }

        .metric-card--lift {
          border-width: 2px;
        }

        .metric-icon {
          font-size: 2rem;
          line-height: 1;
        }

        .metric-content {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
          flex: 1;
        }

        .metric-label {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
        }

        .metric-value {
          font-size: 2rem;
          font-weight: 700;
          color: rgba(255, 255, 255, 0.95);
          line-height: 1;
        }

        .metric-sublabel {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .lift-visualization {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 1.5rem;
        }

        .lift-bar-container {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .lift-bar-track {
          width: 100%;
          height: 24px;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 12px;
          overflow: hidden;
          position: relative;
        }

        .lift-bar-fill {
          height: 100%;
          border-radius: 12px;
          transition: width 0.6s ease, background-color 0.3s;
          position: relative;
        }

        .lift-bar-fill::after {
          content: '';
          position: absolute;
          inset: 0;
          background: linear-gradient(
            90deg,
            transparent,
            rgba(255, 255, 255, 0.2),
            transparent
          );
          animation: shimmer 2s infinite;
        }

        @keyframes shimmer {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(100%);
          }
        }

        .lift-bar-labels {
          display: flex;
          justify-content: space-between;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .metrics-insight {
          background: rgba(59, 130, 246, 0.05);
          border: 1px solid rgba(59, 130, 246, 0.2);
          border-radius: 8px;
          padding: 1.5rem;
        }

        .metrics-insight h5 {
          margin: 0 0 0.75rem 0;
          font-size: 0.875rem;
          font-weight: 600;
          color: #3b82f6;
          text-transform: uppercase;
        }

        .metrics-insight p {
          margin: 0;
          font-size: 0.875rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.85);
        }

        .metrics-insight strong {
          color: rgba(255, 255, 255, 0.95);
          font-weight: 600;
        }
      `}</style>
    </div>
  );
}
