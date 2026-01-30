/**
 * Brand Beliefs History Component
 *
 * Displays accumulated brand beliefs with:
 * - Timeline visualization
 * - Confidence trends
 * - Actionable recommendations
 * - Evidence links
 */

import React, { useEffect, useState } from "react";
import { BeliefCard } from "./BeliefCard";
import { BeliefTrendChart } from "./BeliefTrendChart";

interface Belief {
  id: string;
  brand_id: string;
  product_id?: string;
  hypothesis: Record<string, any>;
  evidence: Record<string, any>;
  recommendation: string;
  confidence: number;
  metadata: Record<string, any>;
  created_at: string;
}

interface BrandBeliefsProps {
  brandId: string;
  clientId?: string;
  userId?: string;
  limit?: number;
}

export function BrandBeliefs({
  brandId,
  clientId,
  userId,
  limit = 50,
}: BrandBeliefsProps) {
  const [beliefs, setBeliefs] = useState<Belief[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"list" | "timeline" | "trends">("list");

  useEffect(() => {
    const fetchBeliefs = async () => {
      try {
        setLoading(true);
        const params = new URLSearchParams({
          brand_id: brandId,
          limit: limit.toString(),
        });
        if (clientId) params.append("client_id", clientId);
        if (userId) params.append("user_id", userId);

        const response = await fetch(`/api/beliefs?${params}`);
        if (!response.ok) throw new Error("Failed to fetch beliefs");

        const data = await response.json();
        setBeliefs(data.beliefs || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    if (brandId) {
      void fetchBeliefs();
    }
  }, [brandId, clientId, userId, limit]);

  if (loading) {
    return (
      <div className="panel__card">
        <div className="panel__header">
          <h4>Brand Beliefs</h4>
        </div>
        <div className="panel__form">
          <p className="loading-text">Loading beliefs...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel__card">
        <div className="panel__header">
          <h4>Brand Beliefs</h4>
        </div>
        <div className="panel__form">
          <p className="error-text">Error: {error}</p>
        </div>
      </div>
    );
  }

  if (beliefs.length === 0) {
    return (
      <div className="panel__card">
        <div className="panel__header">
          <h4>Brand Beliefs</h4>
        </div>
        <div className="panel__form">
          <div className="empty-state">
            <p>No beliefs yet</p>
            <p className="empty-state__subtitle">
              Run experiments to start building brand knowledge
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel__card">
      <div className="panel__header">
        <div className="beliefs__header">
          <h4>Brand Beliefs</h4>
          <span className="beliefs__badge">Belief Update Agent</span>
        </div>
        <div className="beliefs__view-toggle">
          <button
            type="button"
            className={`toggle-btn ${viewMode === "list" ? "active" : ""}`}
            onClick={() => setViewMode("list")}
          >
            List
          </button>
          <button
            type="button"
            className={`toggle-btn ${viewMode === "timeline" ? "active" : ""}`}
            onClick={() => setViewMode("timeline")}
          >
            Timeline
          </button>
          <button
            type="button"
            className={`toggle-btn ${viewMode === "trends" ? "active" : ""}`}
            onClick={() => setViewMode("trends")}
          >
            Trends
          </button>
        </div>
      </div>

      <div className="panel__form">
        {/* Summary Stats */}
        <div className="beliefs__stats">
          <div className="stat">
            <span className="stat__label">Total Beliefs</span>
            <span className="stat__value">{beliefs.length}</span>
          </div>
          <div className="stat">
            <span className="stat__label">Avg Confidence</span>
            <span className="stat__value">
              {(
                beliefs.reduce((sum, b) => sum + b.confidence, 0) / beliefs.length
              ).toFixed(1)}
              %
            </span>
          </div>
          <div className="stat">
            <span className="stat__label">High Confidence</span>
            <span className="stat__value">
              {beliefs.filter((b) => b.confidence >= 0.7).length}
            </span>
          </div>
        </div>

        {/* Trend Chart View */}
        {viewMode === "trends" && <BeliefTrendChart beliefs={beliefs} />}

        {/* Timeline View */}
        {viewMode === "timeline" && (
          <div className="beliefs__timeline">
            {beliefs.map((belief, index) => (
              <div key={belief.id} className="timeline-item">
                <div className="timeline-marker">
                  <div
                    className="timeline-dot"
                    style={{
                      backgroundColor:
                        belief.confidence >= 0.7
                          ? "#1cc886"
                          : belief.confidence >= 0.5
                            ? "#fbbf24"
                            : "#fb923c",
                    }}
                  />
                  {index < beliefs.length - 1 && <div className="timeline-line" />}
                </div>
                <div className="timeline-content">
                  <BeliefCard belief={belief} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* List View */}
        {viewMode === "list" && (
          <div className="beliefs__list">
            {beliefs.map((belief) => (
              <BeliefCard key={belief.id} belief={belief} />
            ))}
          </div>
        )}
      </div>

      <style jsx>{`
        .beliefs__header {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .beliefs__badge {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 0.25rem 0.6rem;
          font-size: 0.65rem;
          font-weight: 600;
          letter-spacing: 0.02em;
          text-transform: uppercase;
          color: #1cc886;
          border: 1px solid rgba(28, 200, 134, 0.4);
          background: rgba(28, 200, 134, 0.08);
        }

        .beliefs__view-toggle {
          display: flex;
          gap: 0.5rem;
        }

        .toggle-btn {
          padding: 0.5rem 1rem;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          color: rgba(255, 255, 255, 0.7);
          cursor: pointer;
          font-size: 0.875rem;
          transition: all 0.2s;
        }

        .toggle-btn:hover {
          background: rgba(255, 255, 255, 0.1);
          color: rgba(255, 255, 255, 0.9);
        }

        .toggle-btn.active {
          background: #1cc886;
          border-color: #1cc886;
          color: white;
        }

        .beliefs__stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 1rem;
          margin-bottom: 2rem;
          padding-bottom: 1.5rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .stat {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .stat__label {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: rgba(255, 255, 255, 0.6);
        }

        .stat__value {
          font-size: 1.5rem;
          font-weight: 700;
          color: #1cc886;
        }

        .beliefs__timeline {
          display: flex;
          flex-direction: column;
          gap: 0;
        }

        .timeline-item {
          display: grid;
          grid-template-columns: 40px 1fr;
          gap: 1rem;
        }

        .timeline-marker {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding-top: 0.5rem;
        }

        .timeline-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          box-shadow: 0 0 0 4px rgba(28, 200, 134, 0.2);
        }

        .timeline-line {
          width: 2px;
          flex: 1;
          background: rgba(255, 255, 255, 0.1);
          margin: 0.5rem 0;
        }

        .timeline-content {
          padding-bottom: 1.5rem;
        }

        .beliefs__list {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .loading-text,
        .error-text {
          text-align: center;
          padding: 2rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .error-text {
          color: #fb923c;
        }

        .empty-state {
          text-align: center;
          padding: 3rem 1rem;
        }

        .empty-state p {
          margin: 0;
          color: rgba(255, 255, 255, 0.6);
        }

        .empty-state__subtitle {
          margin-top: 0.5rem;
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.4);
        }
      `}</style>
    </div>
  );
}
