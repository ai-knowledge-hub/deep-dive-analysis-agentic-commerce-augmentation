"use client";

import React, { type ReactNode } from "react";
import type {
  TimelineEventFilter,
  TimelinePresetId,
  TimelineStatusFilter,
  TimelineWindowFilter,
} from "./timelineFilters";
import { TIMELINE_PRESETS } from "./timelineFilters";

export type AgentTimelineEventView = {
  id: string;
  actionId?: string | null;
  sequence?: number | null;
  capability: string;
  status: string;
  when?: string | null;
  note?: string | null;
  toolId?: string | null;
  skillId?: string | null;
  effectClass?: string | null;
  isPolicy?: boolean;
  anchors?: {
    experiment_id?: string | null;
    validation_job_id?: string | null;
  };
};

type Props = {
  events: AgentTimelineEventView[];
  actionCount: number;
  livePollingActive: boolean;
  hasMoreBefore?: boolean;
  loadingOlderEvents: boolean;
  loading: boolean;
  selectedEventId?: string | null;
  timelinePreset: TimelinePresetId;
  timelineFilter: TimelineEventFilter;
  timelineStatusFilter: TimelineStatusFilter;
  timelineCapabilityFilter: string;
  timelineCapabilityOptions: string[];
  timelineTimeWindow: TimelineWindowFilter;
  copyLinkNotice?: { type: "info" | "error"; text: string } | null;
  onLoadOlderEvents: () => void;
  onApplyTimelinePreset: (presetId: Exclude<TimelinePresetId, "custom">) => void;
  onTimelineFilterChange: (value: TimelineEventFilter) => void;
  onTimelineStatusFilterChange: (value: TimelineStatusFilter) => void;
  onTimelineCapabilityFilterChange: (value: string) => void;
  onTimelineTimeWindowChange: (value: TimelineWindowFilter) => void;
  onSelectEvent: (eventId: string) => void;
  onFocusAction: (event: AgentTimelineEventView) => void;
  canOpenExperiment: (event: AgentTimelineEventView) => boolean;
  onOpenExperiment: (event: AgentTimelineEventView) => void;
  canOpenValidation: (event: AgentTimelineEventView) => boolean;
  onOpenValidation: (event: AgentTimelineEventView) => void;
  onCopyEventLink: (event: AgentTimelineEventView) => void;
};

export function AgentTimelinePanel({
  events,
  actionCount,
  livePollingActive,
  hasMoreBefore,
  loadingOlderEvents,
  loading,
  selectedEventId,
  timelinePreset,
  timelineFilter,
  timelineStatusFilter,
  timelineCapabilityFilter,
  timelineCapabilityOptions,
  timelineTimeWindow,
  copyLinkNotice,
  onLoadOlderEvents,
  onApplyTimelinePreset,
  onTimelineFilterChange,
  onTimelineStatusFilterChange,
  onTimelineCapabilityFilterChange,
  onTimelineTimeWindowChange,
  onSelectEvent,
  onFocusAction,
  canOpenExperiment,
  onOpenExperiment,
  canOpenValidation,
  onOpenValidation,
  onCopyEventLink,
}: Props) {
  return (
    <section className="agent-timeline control-section">
      <div className="control-section__header">
        <div>
          <span className="control-section__eyebrow">Timeline</span>
          <h4 className="control-section__title">Execution timeline</h4>
        </div>
        <div className="panel__row panel__row--compact">
          <span className="control-chip">
            {events.length}/{actionCount} events
          </span>
          <span className="control-chip">Live: {livePollingActive ? "on" : "paused"}</span>
          {hasMoreBefore ? (
            <button
              type="button"
              className="button button--ghost button--sm"
              onClick={onLoadOlderEvents}
              disabled={loadingOlderEvents || loading}
            >
              {loadingOlderEvents ? "Loading..." : "Load older events"}
            </button>
          ) : null}
        </div>
      </div>
      <div className="agent-timeline__filters">
        {TIMELINE_PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={`button button--ghost button--sm ${
              timelinePreset === preset.id ? "is-active" : ""
            }`}
            onClick={() => onApplyTimelinePreset(preset.id)}
          >
            {preset.label}
          </button>
        ))}
        {timelinePreset === "custom" ? (
          <span className="panel__badge panel__badge--secondary">Custom view</span>
        ) : null}
      </div>
      {copyLinkNotice ? (
        <div
          className={`panel__notice ${
            copyLinkNotice.type === "error" ? "panel__notice--error" : "panel__notice--info"
          }`}
        >
          {copyLinkNotice.text}
        </div>
      ) : null}
      <details className="panel__details agent-timeline__advanced-filters">
        <summary className="panel__details-summary">More timeline filters</summary>
        <div className="agent-timeline__filters">
          {(["all", "failed", "policy", "command", "executed"] as TimelineEventFilter[]).map(
            (filter) => (
              <button
                key={filter}
                type="button"
                className={`button button--ghost button--sm ${
                  timelineFilter === filter ? "is-active" : ""
                }`}
                onClick={() => onTimelineFilterChange(filter)}
              >
                {filter === "all" ? "All" : filter === "command" ? "Commands" : titleCase(filter)}
              </button>
            ),
          )}
          <select
            aria-label="Timeline status filter"
            className="input"
            style={{ minWidth: 170 }}
            value={timelineStatusFilter}
            onChange={(event) =>
              onTimelineStatusFilterChange(event.target.value as TimelineStatusFilter)
            }
          >
            <option value="all">All statuses</option>
            <option value="proposed">Proposed</option>
            <option value="approved">Approved</option>
            <option value="executing">Executing</option>
            <option value="executed">Executed</option>
            <option value="failed">Failed</option>
            <option value="rejected">Rejected</option>
          </select>
          <select
            aria-label="Timeline action filter"
            className="input"
            style={{ minWidth: 220 }}
            value={timelineCapabilityFilter}
            onChange={(event) => onTimelineCapabilityFilterChange(event.target.value)}
          >
            {timelineCapabilityOptions.map((item) => (
              <option key={item} value={item}>
                {item === "all" ? "All actions" : item}
              </option>
            ))}
          </select>
          <select
            aria-label="Timeline window filter"
            className="input"
            style={{ minWidth: 160 }}
            value={timelineTimeWindow}
            onChange={(event) =>
              onTimelineTimeWindowChange(event.target.value as TimelineWindowFilter)
            }
          >
            <option value="all">All time</option>
            <option value="24h">Last 24h</option>
            <option value="7d">Last 7d</option>
          </select>
        </div>
      </details>
      {events.length === 0 ? (
        <p className="panel__muted">No timeline events yet.</p>
      ) : (
        <div className="agent-timeline__list">
          {events.map((event) => (
            <TimelineEventItem
              key={event.id}
              event={event}
              isSelected={selectedEventId === event.id}
              canOpenExperiment={canOpenExperiment(event)}
              canOpenValidation={canOpenValidation(event)}
              onSelect={() => onSelectEvent(event.id)}
              onFocusAction={() => onFocusAction(event)}
              onOpenExperiment={() => onOpenExperiment(event)}
              onOpenValidation={() => onOpenValidation(event)}
              onCopyLink={() => onCopyEventLink(event)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function TimelineEventItem({
  event,
  isSelected,
  canOpenExperiment,
  canOpenValidation,
  onSelect,
  onFocusAction,
  onOpenExperiment,
  onOpenValidation,
  onCopyLink,
}: {
  event: AgentTimelineEventView;
  isSelected: boolean;
  canOpenExperiment: boolean;
  canOpenValidation: boolean;
  onSelect: () => void;
  onFocusAction: () => void;
  onOpenExperiment: () => void;
  onOpenValidation: () => void;
  onCopyLink: () => void;
}) {
  return (
    <div
      id={`agent-event-${event.id}`}
      className={`agent-timeline__item ${isSelected ? "is-focused" : ""}`}
      onClick={onSelect}
    >
      <div className="agent-timeline__meta">
        <span className="agent-timeline__seq">#{event.sequence}</span>
        <span className="agent-timeline__cap">{event.capability}</span>
        <span className={`agent-timeline__status is-${event.status}`}>{event.status}</span>
        <span className="agent-timeline__time">
          {event.when ? new Date(event.when).toLocaleString() : "time unavailable"}
        </span>
      </div>
      {event.skillId || event.toolId || event.effectClass ? (
        <details className="panel__details agent-timeline__technical">
          <summary className="panel__details-summary">Technical event detail</summary>
          <div className="panel__meta">
            {event.skillId ? (
              <span className="panel__badge panel__badge--secondary">Skill: {event.skillId}</span>
            ) : null}
            {event.toolId ? (
              <span className="panel__badge panel__badge--secondary">Tool: {event.toolId}</span>
            ) : null}
            {event.effectClass ? (
              <span className="panel__badge panel__badge--secondary">
                Effect: {event.effectClass}
              </span>
            ) : null}
          </div>
        </details>
      ) : null}
      <div className="agent-timeline__actions">
        {event.actionId ? (
          <TimelineButton onClick={onFocusAction}>Focus action</TimelineButton>
        ) : null}
        {canOpenExperiment ? (
          <TimelineButton onClick={onOpenExperiment}>Open experiment</TimelineButton>
        ) : null}
        {canOpenValidation ? (
          <TimelineButton onClick={onOpenValidation}>Open validation</TimelineButton>
        ) : null}
        <TimelineButton onClick={onCopyLink}>Copy link</TimelineButton>
      </div>
      {event.note ? (
        <p className={`agent-timeline__note ${event.isPolicy ? "is-policy" : ""}`}>
          {event.note}
        </p>
      ) : null}
    </div>
  );
}

function TimelineButton({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="button button--ghost button--sm"
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
    >
      {children}
    </button>
  );
}

function titleCase(value: string) {
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}
