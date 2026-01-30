/**
 * Statistical Analysis Visualization Component
 *
 * Displays statistical comparison results including:
 * - Effect size with interpretation
 * - Confidence intervals
 * - P-value with significance indicator
 * - Recommended action
 */

import React from "react";

interface StatisticalAnalysisProps {
  analysis: {
    variant_a_id: string;
    variant_b_id: string;
    metric_name: string;
    difference: number;
    effect_size: number;
    confidence_interval: [number, number];
    p_value: number;
    is_significant: boolean;
    recommended_action: string;
  };
  variantLabels?: Map<string, string>;
}

export function StatisticalAnalysis({
  analysis,
  variantLabels,
}: StatisticalAnalysisProps) {
  const getEffectSizeInterpretation = (effectSize: number): string => {
    const abs = Math.abs(effectSize);
    if (abs < 0.2) return "negligible";
    if (abs < 0.5) return "small";
    if (abs < 0.8) return "medium";
    return "large";
  };

  const getEffectSizeColor = (effectSize: number): string => {
    const abs = Math.abs(effectSize);
    if (abs < 0.2) return "#94a3b8"; // gray
    if (abs < 0.5) return "#fbbf24"; // yellow
    if (abs < 0.8) return "#fb923c"; // orange
    return "#1cc886"; // green
  };

  const variantALabel =
    variantLabels?.get(analysis.variant_a_id) || analysis.variant_a_id;
  const variantBLabel =
    variantLabels?.get(analysis.variant_b_id) || analysis.variant_b_id;

  const effectInterpretation = getEffectSizeInterpretation(analysis.effect_size);
  const effectColor = getEffectSizeColor(analysis.effect_size);

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h4>Statistical Analysis</h4>
        <span
          className={`panel__badge ${
            analysis.is_significant
              ? "panel__badge--success"
              : "panel__badge--secondary"
          }`}
        >
          {analysis.is_significant ? "Significant" : "Not Significant"}
        </span>
      </div>

      <div className="panel__form">
        <div className="stats-grid">
          {/* Comparison */}
          <div className="stats-section">
            <h5 className="stats-label">Comparing</h5>
            <div className="stats-comparison">
              <span className="stats-variant">{variantALabel}</span>
              <span className="stats-vs">vs</span>
              <span className="stats-variant">{variantBLabel}</span>
            </div>
          </div>

          {/* Difference */}
          <div className="stats-section">
            <h5 className="stats-label">Difference</h5>
            <div className="stats-value">
              <span className="stats-number">
                {analysis.difference > 0 ? "+" : ""}
                {(analysis.difference * 100).toFixed(1)}%
              </span>
              <span className="stats-subtext">
                {variantBLabel} {analysis.difference > 0 ? "better" : "worse"}
              </span>
            </div>
          </div>

          {/* Effect Size */}
          <div className="stats-section">
            <h5 className="stats-label">Effect Size (Cohen&apos;s d)</h5>
            <div className="stats-value">
              <span className="stats-number" style={{ color: effectColor }}>
                {analysis.effect_size.toFixed(2)}
              </span>
              <span className="stats-subtext">{effectInterpretation}</span>
            </div>
            <div className="effect-size-bar">
              <div
                className="effect-size-fill"
                style={{
                  width: `${Math.min(Math.abs(analysis.effect_size) * 50, 100)}%`,
                  backgroundColor: effectColor,
                }}
              />
            </div>
          </div>

          {/* P-Value */}
          <div className="stats-section">
            <h5 className="stats-label">P-Value</h5>
            <div className="stats-value">
              <span
                className="stats-number"
                style={{
                  color: analysis.p_value < 0.05 ? "#1cc886" : "#94a3b8",
                }}
              >
                {analysis.p_value.toFixed(4)}
              </span>
              <span className="stats-subtext">
                {analysis.p_value < 0.01
                  ? "highly significant"
                  : analysis.p_value < 0.05
                    ? "significant"
                    : "not significant"}
              </span>
            </div>
          </div>

          {/* Confidence Interval */}
          <div className="stats-section">
            <h5 className="stats-label">95% Confidence Interval</h5>
            <div className="stats-value">
              <span className="stats-number">
                [{(analysis.confidence_interval[0] * 100).toFixed(1)}%,{" "}
                {(analysis.confidence_interval[1] * 100).toFixed(1)}%]
              </span>
              <span className="stats-subtext">true difference range</span>
            </div>
            <div className="confidence-interval-bar">
              <div className="ci-marker" style={{ left: "50%" }} />
              <div
                className="ci-range"
                style={{
                  left: `${(analysis.confidence_interval[0] + 0.5) * 100}%`,
                  width: `${(analysis.confidence_interval[1] - analysis.confidence_interval[0]) * 100}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* Recommendation */}
        <div className="stats-recommendation">
          <strong>Recommendation:</strong> {analysis.recommended_action}
        </div>
      </div>

      <style jsx>{`
        .stats-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 1.5rem;
        }

        .stats-section {
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          padding-bottom: 1rem;
        }

        .stats-section:last-child {
          border-bottom: none;
        }

        .stats-label {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
          margin: 0 0 0.5rem 0;
        }

        .stats-comparison {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .stats-variant {
          font-weight: 600;
          color: #1cc886;
        }

        .stats-vs {
          color: rgba(255, 255, 255, 0.4);
          font-size: 0.875rem;
        }

        .stats-value {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }

        .stats-number {
          font-size: 1.5rem;
          font-weight: 700;
        }

        .stats-subtext {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .effect-size-bar {
          margin-top: 0.5rem;
          height: 8px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          overflow: hidden;
        }

        .effect-size-fill {
          height: 100%;
          transition: width 0.3s ease;
        }

        .confidence-interval-bar {
          position: relative;
          margin-top: 0.5rem;
          height: 8px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
        }

        .ci-marker {
          position: absolute;
          top: 0;
          width: 2px;
          height: 8px;
          background: rgba(255, 255, 255, 0.4);
          transform: translateX(-50%);
        }

        .ci-range {
          position: absolute;
          top: 0;
          height: 8px;
          background: rgba(28, 200, 134, 0.6);
          border-radius: 4px;
        }

        .stats-recommendation {
          margin-top: 1.5rem;
          padding: 1rem;
          background: rgba(28, 200, 134, 0.1);
          border-left: 3px solid #1cc886;
          border-radius: 4px;
          font-size: 0.875rem;
          line-height: 1.5;
        }

        .stats-recommendation strong {
          color: #1cc886;
        }
      `}</style>
    </div>
  );
}
