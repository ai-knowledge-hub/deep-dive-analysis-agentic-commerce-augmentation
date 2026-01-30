/**
 * ML Prediction Visualization Component
 *
 * Displays ML-based hypothesis recommendation including:
 * - Predicted lift
 * - Confidence score
 * - Rationale
 * - Similar past experiments
 */

import React from "react";

interface MLPredictionProps {
  prediction: {
    hypothesis_type: string;
    predicted_lift: number;
    confidence: number;
    rationale: string;
    similar_experiments?: string[];
  };
}

export function MLPrediction({ prediction }: MLPredictionProps) {
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

  const confidenceColor = getConfidenceColor(prediction.confidence);
  const confidenceLabel = getConfidenceLabel(prediction.confidence);
  const confidencePercentage = Math.round(prediction.confidence * 100);

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h4>ML Prediction</h4>
        <span
          className="panel__badge"
          style={{ backgroundColor: confidenceColor }}
        >
          {confidenceLabel}
        </span>
      </div>

      <div className="panel__form">
        <div className="ml-grid">
          {/* Hypothesis Type */}
          <div className="ml-section">
            <h5 className="ml-label">Recommended Intervention</h5>
            <div className="ml-value">
              <span className="ml-type-badge">{prediction.hypothesis_type}</span>
            </div>
          </div>

          {/* Predicted Lift */}
          <div className="ml-section">
            <h5 className="ml-label">Predicted Lift</h5>
            <div className="ml-value">
              <span className="ml-number">
                +{(prediction.predicted_lift * 100).toFixed(1)}%
              </span>
              <span className="ml-subtext">expected improvement</span>
            </div>
            <div className="lift-bar">
              <div
                className="lift-fill"
                style={{
                  width: `${Math.min(prediction.predicted_lift * 500, 100)}%`,
                }}
              />
            </div>
          </div>

          {/* Confidence */}
          <div className="ml-section">
            <h5 className="ml-label">Prediction Confidence</h5>
            <div className="ml-value">
              <span className="ml-number" style={{ color: confidenceColor }}>
                {confidencePercentage}%
              </span>
              <span className="ml-subtext">{confidenceLabel.toLowerCase()}</span>
            </div>
            <div className="confidence-bar">
              <div
                className="confidence-fill"
                style={{
                  width: `${confidencePercentage}%`,
                  backgroundColor: confidenceColor,
                }}
              />
            </div>
          </div>

          {/* Similar Experiments */}
          {prediction.similar_experiments &&
            prediction.similar_experiments.length > 0 && (
              <div className="ml-section">
                <h5 className="ml-label">Based on Similar Experiments</h5>
                <div className="ml-value">
                  <span className="ml-number">
                    {prediction.similar_experiments.length}
                  </span>
                  <span className="ml-subtext">past experiments analyzed</span>
                </div>
                <div className="similar-experiments">
                  {prediction.similar_experiments.slice(0, 5).map((expId, idx) => (
                    <span key={expId} className="experiment-badge">
                      #{idx + 1}
                    </span>
                  ))}
                  {prediction.similar_experiments.length > 5 && (
                    <span className="experiment-badge">
                      +{prediction.similar_experiments.length - 5} more
                    </span>
                  )}
                </div>
              </div>
            )}
        </div>

        {/* Rationale */}
        <div className="ml-rationale">
          <h5 className="ml-label">Why This Recommendation?</h5>
          <p>{prediction.rationale}</p>
        </div>
      </div>

      <style jsx>{`
        .ml-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 1.5rem;
        }

        .ml-section {
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          padding-bottom: 1rem;
        }

        .ml-section:last-child {
          border-bottom: none;
        }

        .ml-label {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
          margin: 0 0 0.5rem 0;
        }

        .ml-value {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }

        .ml-type-badge {
          display: inline-block;
          padding: 0.25rem 0.75rem;
          background: rgba(28, 200, 134, 0.2);
          color: #1cc886;
          border-radius: 12px;
          font-size: 0.875rem;
          font-weight: 600;
          text-transform: capitalize;
        }

        .ml-number {
          font-size: 1.5rem;
          font-weight: 700;
        }

        .ml-subtext {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .lift-bar,
        .confidence-bar {
          margin-top: 0.5rem;
          height: 8px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          overflow: hidden;
        }

        .lift-fill {
          height: 100%;
          background: linear-gradient(90deg, #1cc886, #10b981);
          transition: width 0.3s ease;
        }

        .confidence-fill {
          height: 100%;
          transition: width 0.3s ease, background-color 0.3s ease;
        }

        .similar-experiments {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          margin-top: 0.5rem;
        }

        .experiment-badge {
          display: inline-block;
          padding: 0.25rem 0.5rem;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          font-size: 0.75rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.8);
        }

        .ml-rationale {
          margin-top: 1.5rem;
          padding: 1rem;
          background: rgba(59, 130, 246, 0.1);
          border-left: 3px solid #3b82f6;
          border-radius: 4px;
        }

        .ml-rationale h5 {
          margin: 0 0 0.75rem 0;
          color: #3b82f6;
        }

        .ml-rationale p {
          margin: 0;
          font-size: 0.875rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.9);
        }
      `}</style>
    </div>
  );
}
