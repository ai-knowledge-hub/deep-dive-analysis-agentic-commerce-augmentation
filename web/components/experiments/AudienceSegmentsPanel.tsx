"use client";

import React from "react";
import type { AudienceSegment } from "../../lib/types";

type Props = {
  open: boolean;
  status: string | null;
  segments: AudienceSegment[];
  onOpenChange: (open: boolean) => void;
  onSegmentToggle: (segmentId: string, active: boolean) => void;
};

export function AudienceSegmentsPanel({
  open,
  status,
  segments,
  onOpenChange,
  onSegmentToggle,
}: Props) {
  return (
    <details
      open={open}
      onToggle={(event) => onOpenChange(event.currentTarget.open)}
      className="panel__card"
    >
      <summary className="panel__label">Audience segments for top-down generation</summary>
      <p className="panel__muted">
        These are session-derived behavioral segments used to condition top-down/hybrid query
        generation. Disable any segment to exclude it.
      </p>
      {status ? <p className="panel__status">{status}</p> : null}
      {segments.length === 0 ? (
        <div className="panel__notice panel__notice--info">
          No session-derived segments yet. Fallback stays active: canonical intent spec + product
          metadata + stored archetypes.
        </div>
      ) : (
        <ul className="panel__list">
          {segments.map((segment) => (
            <li key={segment.id}>
              <div className="panel__row" style={{ justifyContent: "space-between" }}>
                <div>
                  <strong>{segment.label}</strong>
                  {typeof segment.support === "number" ? (
                    <span className="panel__muted"> · support {segment.support}</span>
                  ) : null}
                  {typeof segment.confidence === "number" ? (
                    <span className="panel__muted">
                      {" "}
                      · confidence {Math.round(segment.confidence * 100)}%
                    </span>
                  ) : null}
                  {segment.description ? (
                    <p className="panel__muted">{segment.description}</p>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => onSegmentToggle(segment.id, !segment.active)}
                >
                  {segment.active ? "Disable" : "Enable"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
