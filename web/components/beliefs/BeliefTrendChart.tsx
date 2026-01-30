/**
 * Belief Trend Chart Component
 *
 * Visualizes belief confidence trends and patterns over time.
 */

import React, { useMemo } from "react";

interface BeliefTrendChartProps {
  beliefs: Array<{
    id: string;
    brand_id: string;
    product_id?: string;
    hypothesis: Record<string, any>;
    evidence: Record<string, any>;
    recommendation: string;
    confidence: number;
    metadata: Record<string, any>;
    created_at: string;
  }>;
}

interface DataPoint {
  date: string;
  timestamp: number;
  confidence: number;
  type: string;
  recommendation: string;
}

export function BeliefTrendChart({ beliefs }: BeliefTrendChartProps) {
  const chartData = useMemo(() => {
    // Convert beliefs to data points
    const points: DataPoint[] = beliefs.map((belief) => ({
      date: new Date(belief.created_at).toLocaleDateString(),
      timestamp: new Date(belief.created_at).getTime(),
      confidence: belief.confidence,
      type: belief.metadata?.variant_type || "unknown",
      recommendation: belief.recommendation,
    }));

    // Sort by timestamp
    return points.sort((a, b) => a.timestamp - b.timestamp);
  }, [beliefs]);

  const stats = useMemo(() => {
    if (chartData.length === 0) return null;

    const confidences = chartData.map((d) => d.confidence);
    const avgConfidence = confidences.reduce((a, b) => a + b, 0) / confidences.length;

    // Calculate trend (simple linear regression slope)
    const n = chartData.length;
    const sumX = chartData.reduce((sum, _, i) => sum + i, 0);
    const sumY = confidences.reduce((sum, c) => sum + c, 0);
    const sumXY = chartData.reduce((sum, d, i) => sum + i * d.confidence, 0);
    const sumX2 = chartData.reduce((sum, _, i) => sum + i * i, 0);

    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const trend = slope > 0.01 ? "improving" : slope < -0.01 ? "declining" : "stable";

    // Group by intervention type
    const typeGroups: Record<string, number[]> = {};
    chartData.forEach((point) => {
      if (!typeGroups[point.type]) typeGroups[point.type] = [];
      typeGroups[point.type].push(point.confidence);
    });

    const typeAvgs = Object.entries(typeGroups).map(([type, confidences]) => ({
      type,
      avgConfidence: confidences.reduce((a, b) => a + b, 0) / confidences.length,
      count: confidences.length,
    }));

    typeAvgs.sort((a, b) => b.avgConfidence - a.avgConfidence);

    return {
      avgConfidence,
      trend,
      slope,
      typeAvgs,
    };
  }, [chartData]);

  if (chartData.length === 0) {
    return (
      <div className="trend-chart-empty">
        <p>No belief data available to visualize trends.</p>
      </div>
    );
  }

  const maxConfidence = Math.max(...chartData.map((d) => d.confidence));
  const minConfidence = Math.min(...chartData.map((d) => d.confidence));

  return (
    <div className="belief-trend-chart">
      {/* Summary Stats */}
      <div className="trend-stats">
        <div className="stat-card">
          <span className="stat-label">Average Confidence</span>
          <span className="stat-value">
            {stats ? (stats.avgConfidence * 100).toFixed(1) : 0}%
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Trend</span>
          <span className={`stat-value trend-${stats?.trend}`}>
            {stats?.trend === "improving" && "↗ Improving"}
            {stats?.trend === "declining" && "↘ Declining"}
            {stats?.trend === "stable" && "→ Stable"}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Beliefs</span>
          <span className="stat-value">{chartData.length}</span>
        </div>
      </div>

      {/* Confidence Over Time Chart */}
      <div className="chart-section">
        <h6>Confidence Over Time</h6>
        <div className="chart-container">
          <div className="chart-y-axis">
            <span>100%</span>
            <span>75%</span>
            <span>50%</span>
            <span>25%</span>
            <span>0%</span>
          </div>
          <div className="chart-area">
            {/* Grid lines */}
            <div className="chart-grid">
              <div className="grid-line" />
              <div className="grid-line" />
              <div className="grid-line" />
              <div className="grid-line" />
              <div className="grid-line" />
            </div>

            {/* Data points */}
            <svg className="chart-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
              {/* Line connecting points */}
              <polyline
                points={chartData
                  .map((d, i) => {
                    const x = (i / (chartData.length - 1)) * 100;
                    const y = 100 - d.confidence * 100;
                    return `${x},${y}`;
                  })
                  .join(" ")}
                fill="none"
                stroke="#1cc886"
                strokeWidth="0.5"
                opacity="0.6"
              />

              {/* Trend line */}
              {stats && stats.slope !== 0 && (
                <line
                  x1="0"
                  y1={100 - (stats.avgConfidence - stats.slope * (chartData.length / 2)) * 100}
                  x2="100"
                  y2={100 - (stats.avgConfidence + stats.slope * (chartData.length / 2)) * 100}
                  stroke="#fbbf24"
                  strokeWidth="0.3"
                  strokeDasharray="2,2"
                  opacity="0.5"
                />
              )}
            </svg>

            {/* Points overlay */}
            <div className="chart-points">
              {chartData.map((point, i) => {
                const x = (i / (chartData.length - 1)) * 100;
                const y = 100 - point.confidence * 100;

                return (
                  <div
                    key={i}
                    className="chart-point"
                    style={{
                      left: `${x}%`,
                      top: `${y}%`,
                    }}
                    title={`${point.date}: ${(point.confidence * 100).toFixed(1)}% - ${point.recommendation}`}
                  >
                    <div className="point-dot" />
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* X-axis labels */}
        <div className="chart-x-axis">
          <span>{chartData[0]?.date}</span>
          {chartData.length > 1 && <span>{chartData[chartData.length - 1]?.date}</span>}
        </div>
      </div>

      {/* Intervention Type Performance */}
      {stats && stats.typeAvgs.length > 0 && (
        <div className="type-performance">
          <h6>Performance by Intervention Type</h6>
          <div className="type-bars">
            {stats.typeAvgs.map((typeData) => (
              <div key={typeData.type} className="type-bar-row">
                <div className="type-label">
                  <span className="type-name">{typeData.type}</span>
                  <span className="type-count">({typeData.count})</span>
                </div>
                <div className="type-bar-container">
                  <div
                    className="type-bar-fill"
                    style={{
                      width: `${typeData.avgConfidence * 100}%`,
                      backgroundColor:
                        typeData.avgConfidence >= 0.7
                          ? "#1cc886"
                          : typeData.avgConfidence >= 0.5
                          ? "#fbbf24"
                          : "#fb923c",
                    }}
                  />
                  <span className="type-bar-value">
                    {(typeData.avgConfidence * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <style jsx>{`
        .belief-trend-chart {
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }

        .trend-chart-empty {
          padding: 3rem;
          text-align: center;
          color: rgba(255, 255, 255, 0.5);
        }

        .trend-stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 1rem;
        }

        .stat-card {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 1rem;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .stat-label {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
        }

        .stat-value {
          font-size: 1.5rem;
          font-weight: 700;
          color: rgba(255, 255, 255, 0.95);
        }

        .trend-improving {
          color: #1cc886;
        }

        .trend-declining {
          color: #fb923c;
        }

        .trend-stable {
          color: #fbbf24;
        }

        .chart-section {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 1.5rem;
        }

        .chart-section h6 {
          margin: 0 0 1rem 0;
          font-size: 0.875rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.7);
        }

        .chart-container {
          display: flex;
          gap: 1rem;
          height: 200px;
        }

        .chart-y-axis {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
          padding-right: 0.5rem;
        }

        .chart-area {
          flex: 1;
          position: relative;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          background: rgba(0, 0, 0, 0.2);
        }

        .chart-grid {
          position: absolute;
          inset: 0;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          pointer-events: none;
        }

        .grid-line {
          height: 1px;
          background: rgba(255, 255, 255, 0.05);
        }

        .chart-svg {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
        }

        .chart-points {
          position: absolute;
          inset: 0;
        }

        .chart-point {
          position: absolute;
          transform: translate(-50%, -50%);
          cursor: pointer;
          z-index: 1;
        }

        .point-dot {
          width: 8px;
          height: 8px;
          background: #1cc886;
          border: 2px solid rgba(0, 0, 0, 0.5);
          border-radius: 50%;
          transition: all 0.2s;
        }

        .chart-point:hover .point-dot {
          width: 12px;
          height: 12px;
          background: #fbbf24;
        }

        .chart-x-axis {
          display: flex;
          justify-content: space-between;
          margin-top: 0.5rem;
          padding-left: 3rem;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .type-performance {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 1.5rem;
        }

        .type-performance h6 {
          margin: 0 0 1rem 0;
          font-size: 0.875rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.7);
        }

        .type-bars {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .type-bar-row {
          display: flex;
          align-items: center;
          gap: 1rem;
        }

        .type-label {
          min-width: 120px;
          display: flex;
          align-items: baseline;
          gap: 0.5rem;
        }

        .type-name {
          font-size: 0.875rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.9);
          text-transform: capitalize;
        }

        .type-count {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .type-bar-container {
          flex: 1;
          position: relative;
          height: 32px;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 4px;
          overflow: hidden;
        }

        .type-bar-fill {
          height: 100%;
          transition: width 0.3s;
          border-radius: 4px;
        }

        .type-bar-value {
          position: absolute;
          right: 0.75rem;
          top: 50%;
          transform: translateY(-50%);
          font-size: 0.75rem;
          font-weight: 700;
          color: rgba(255, 255, 255, 0.95);
          text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
        }
      `}</style>
    </div>
  );
}
