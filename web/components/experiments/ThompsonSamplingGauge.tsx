/**
 * Thompson Sampling Gauge Component
 *
 * Visualizes the exploration vs exploitation trade-off
 * using Thompson Sampling (Bayesian multi-armed bandit).
 */

import React from "react";

interface ThompsonSamplingGaugeProps {
  explorationScore: number; // 0-1
  exploitationScore: number; // 0-1
  variantLabel?: string;
}

export function ThompsonSamplingGauge({
  explorationScore,
  exploitationScore,
  variantLabel,
}: ThompsonSamplingGaugeProps) {
  const total = explorationScore + exploitationScore;
  const explorationPercentage = total > 0 ? (explorationScore / total) * 100 : 50;
  const exploitationPercentage = total > 0 ? (exploitationScore / total) * 100 : 50;

  const getRecommendation = (): string => {
    if (explorationScore > 0.5) {
      return "High uncertainty — run this variant to gather more data";
    }
    if (explorationScore > 0.3) {
      return "Moderate uncertainty — explore this variant";
    }
    if (exploitationScore > 0.7) {
      return "High performance — exploit this variant";
    }
    return "Balanced — re-run to refine estimates";
  };

  const recommendation = getRecommendation();

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h4>Thompson Sampling Analysis</h4>
        {variantLabel && (
          <span className="panel__badge panel__badge--secondary">
            {variantLabel}
          </span>
        )}
      </div>

      <div className="panel__form">
        <div className="gauge-container">
          <div className="gauge-section">
            <h5 className="gauge-label">Exploration Value</h5>
            <div className="gauge-value">
              <span className="gauge-number">{explorationScore.toFixed(2)}</span>
              <span className="gauge-subtext">
                {explorationScore > 0.5
                  ? "high uncertainty"
                  : explorationScore > 0.3
                    ? "moderate uncertainty"
                    : "low uncertainty"}
              </span>
            </div>
            <div className="gauge-bar">
              <div
                className="gauge-fill exploration-fill"
                style={{ width: `${Math.min(explorationScore * 100, 100)}%` }}
              />
            </div>
          </div>

          <div className="gauge-section">
            <h5 className="gauge-label">Exploitation Value</h5>
            <div className="gauge-value">
              <span className="gauge-number">{exploitationScore.toFixed(2)}</span>
              <span className="gauge-subtext">
                {exploitationScore > 0.7
                  ? "high performance"
                  : exploitationScore > 0.5
                    ? "good performance"
                    : "low performance"}
              </span>
            </div>
            <div className="gauge-bar">
              <div
                className="gauge-fill exploitation-fill"
                style={{ width: `${Math.min(exploitationScore * 100, 100)}%` }}
              />
            </div>
          </div>

          <div className="gauge-section">
            <h5 className="gauge-label">Balance</h5>
            <div className="balance-bar">
              <div
                className="balance-exploration"
                style={{ width: `${explorationPercentage}%` }}
              >
                <span className="balance-label">Explore</span>
              </div>
              <div
                className="balance-exploitation"
                style={{ width: `${exploitationPercentage}%` }}
              >
                <span className="balance-label">Exploit</span>
              </div>
            </div>
            <div className="balance-percentages">
              <span>{explorationPercentage.toFixed(0)}%</span>
              <span>{exploitationPercentage.toFixed(0)}%</span>
            </div>
          </div>
        </div>

        <div className="gauge-recommendation">
          <strong>Strategy:</strong> {recommendation}
        </div>

        <div className="gauge-explanation">
          <p>
            <strong>Thompson Sampling</strong> balances exploration (testing uncertain
            variants) and exploitation (running proven winners). High exploration means
            we need more data; high exploitation means the variant is performing well.
          </p>
        </div>
      </div>

      <style jsx>{`
        .gauge-container {
          display: grid;
          grid-template-columns: 1fr;
          gap: 1.5rem;
        }

        .gauge-section {
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          padding-bottom: 1rem;
        }

        .gauge-section:last-child {
          border-bottom: none;
        }

        .gauge-label {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
          margin: 0 0 0.5rem 0;
        }

        .gauge-value {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }

        .gauge-number {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--text-primary);
        }

        .gauge-subtext {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .gauge-bar {
          margin-top: 0.5rem;
          height: 8px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          overflow: hidden;
        }

        .gauge-fill {
          height: 100%;
          transition: width 0.3s ease;
          background: linear-gradient(
            90deg,
            rgba(16, 185, 129, 0.7),
            rgba(16, 185, 129, 0.95)
          );
        }

        .exploration-fill {
          opacity: 0.75;
        }

        .exploitation-fill {
          opacity: 1;
        }

        .balance-bar {
          display: flex;
          height: 48px;
          border-radius: 4px;
          overflow: hidden;
          margin-top: 0.5rem;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .balance-exploration,
        .balance-exploitation {
          display: flex;
          align-items: center;
          justify-content: center;
          transition: width 0.3s ease;
        }

        .balance-exploration {
          background: rgba(16, 185, 129, 0.32);
        }

        .balance-exploitation {
          background: rgba(16, 185, 129, 0.62);
        }

        .balance-label {
          font-size: 0.75rem;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--text-primary);
        }

        .balance-percentages {
          display: flex;
          justify-content: space-between;
          margin-top: 0.5rem;
          font-size: 0.875rem;
          font-weight: 600;
          color: var(--text-muted);
        }

        .gauge-recommendation {
          margin-top: 1.5rem;
          padding: 1rem;
          background: rgba(255, 255, 255, 0.03);
          border-left: 3px solid rgba(16, 185, 129, 0.65);
          border-radius: 4px;
          font-size: 0.875rem;
          line-height: 1.5;
        }

        .gauge-recommendation strong {
          color: var(--accent);
        }

        .gauge-explanation {
          margin-top: 1rem;
          padding: 1rem;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 4px;
          font-size: 0.8rem;
          line-height: 1.5;
          color: rgba(255, 255, 255, 0.7);
        }

        .gauge-explanation strong {
          color: rgba(255, 255, 255, 0.9);
        }
      `}</style>
    </div>
  );
}
