"use client";

import React from "react";
import { formatOperatorActionName } from "../../lib/operatorDisplayLanguage";
import type { AgentAction } from "../../lib/types";

type DiffBlock = {
  added: { key: string; current: string }[];
  changed: { key: string; current: string; previous: string }[];
  removed: { key: string; previous: string }[];
};

type TextDiffLine = { kind: "same" | "added" | "removed"; text: string };

type CopyDiffEntry = {
  key: string;
  lines: TextDiffLine[];
};

export type ActionDeepDiff = {
  outputsVsPreviousAction: DiffBlock;
  outputsVsPreviousCapability: DiffBlock;
  inputsVsPreviousAction: DiffBlock;
  inputsVsPreviousCapability: DiffBlock;
  currentInputs: Record<string, unknown>;
  currentOutputs: Record<string, unknown>;
  previousOutputs: Record<string, unknown>;
  previousCapabilityOutputs: Record<string, unknown>;
  copyDiffVsPreviousAction: CopyDiffEntry[];
  copyDiffVsPreviousCapability: CopyDiffEntry[];
};

type Props = {
  open: boolean;
  selectedAction: AgentAction | null;
  diff: ActionDeepDiff | null;
  hideUnchangedDiffLines: boolean;
  onHideUnchangedDiffLinesChange: (value: boolean) => void;
  onClose: () => void;
  formatJsonPreview: (value: unknown) => string;
};

function DiffJsonCell({
  title,
  value,
  formatJsonPreview,
}: {
  title: string;
  value: unknown;
  formatJsonPreview: (value: unknown) => string;
}) {
  return (
    <div>
      <strong>{title}</strong>
      <pre className="panel__pre">{formatJsonPreview(value)}</pre>
    </div>
  );
}

function CopyDiffLines({
  entry,
  keyPrefix,
  hideUnchangedDiffLines,
}: {
  entry: CopyDiffEntry;
  keyPrefix: string;
  hideUnchangedDiffLines: boolean;
}) {
  return (
    <details className="agent-copy-diff">
      <summary>{entry.key}</summary>
      <div className="agent-copy-diff__lines">
        {entry.lines
          .filter((line) => (hideUnchangedDiffLines ? line.kind !== "same" : true))
          .map((line, index) => (
            <div
              key={`${keyPrefix}-${entry.key}-${index}`}
              className={`agent-copy-diff__line is-${line.kind}`}
            >
              <span className="agent-copy-diff__prefix">
                {line.kind === "added" ? "+" : line.kind === "removed" ? "-" : " "}
              </span>
              <span className="agent-copy-diff__text">{line.text || " "}</span>
            </div>
          ))}
      </div>
    </details>
  );
}

export function ActionDiffDrawer({
  open,
  selectedAction,
  diff,
  hideUnchangedDiffLines,
  onHideUnchangedDiffLinesChange,
  onClose,
  formatJsonPreview,
}: Props) {
  if (!open || !selectedAction || !diff) return null;

  const hasCopyDiff =
    diff.copyDiffVsPreviousAction.length > 0 ||
    diff.copyDiffVsPreviousCapability.length > 0;

  return (
    <div className="drawer">
      <div className="drawer__overlay" onClick={onClose} />
      <div className="drawer__panel">
        <div className="drawer__header">
          <h2 className="drawer__title">Artifact diff details</h2>
          <button className="drawer__close" onClick={onClose}>
            x
          </button>
        </div>
        <div className="drawer__body">
          <p className="panel__muted">
            Action #{selectedAction.sequence} ·{" "}
            {formatOperatorActionName(selectedAction.capability_name)}
          </p>

          <p className="panel__subheading">Output changes vs previous action</p>
          <div className="agent-diff-detail-grid">
            <DiffJsonCell
              title="Added"
              value={diff.outputsVsPreviousAction.added}
              formatJsonPreview={formatJsonPreview}
            />
            <DiffJsonCell
              title="Changed"
              value={diff.outputsVsPreviousAction.changed}
              formatJsonPreview={formatJsonPreview}
            />
            <DiffJsonCell
              title="Removed"
              value={diff.outputsVsPreviousAction.removed}
              formatJsonPreview={formatJsonPreview}
            />
          </div>

          <p className="panel__subheading">Output changes vs previous same capability</p>
          <div className="agent-diff-detail-grid">
            <DiffJsonCell
              title="Added"
              value={diff.outputsVsPreviousCapability.added}
              formatJsonPreview={formatJsonPreview}
            />
            <DiffJsonCell
              title="Changed"
              value={diff.outputsVsPreviousCapability.changed}
              formatJsonPreview={formatJsonPreview}
            />
            <DiffJsonCell
              title="Removed"
              value={diff.outputsVsPreviousCapability.removed}
              formatJsonPreview={formatJsonPreview}
            />
          </div>

          <p className="panel__subheading">Input changes (traceability)</p>
          <div className="agent-diff-detail-grid">
            <DiffJsonCell
              title="vs previous action"
              value={diff.inputsVsPreviousAction.changed}
              formatJsonPreview={formatJsonPreview}
            />
            <DiffJsonCell
              title="vs previous same capability"
              value={diff.inputsVsPreviousCapability.changed}
              formatJsonPreview={formatJsonPreview}
            />
          </div>

          <p className="panel__subheading">Snapshot payloads</p>
          <div className="agent-diff-detail-grid">
            <DiffJsonCell
              title="Current inputs"
              value={diff.currentInputs}
              formatJsonPreview={formatJsonPreview}
            />
            <DiffJsonCell
              title="Current outputs"
              value={diff.currentOutputs}
              formatJsonPreview={formatJsonPreview}
            />
            <DiffJsonCell
              title="Previous action outputs"
              value={diff.previousOutputs}
              formatJsonPreview={formatJsonPreview}
            />
            <DiffJsonCell
              title="Previous same-capability outputs"
              value={diff.previousCapabilityOutputs}
              formatJsonPreview={formatJsonPreview}
            />
          </div>

          <p className="panel__subheading">Copy diff mode (string-heavy fields)</p>
          <label className="panel__toggle">
            <input
              type="checkbox"
              checked={hideUnchangedDiffLines}
              onChange={(event) => onHideUnchangedDiffLinesChange(event.target.checked)}
            />
            Hide unchanged lines
          </label>
          {!hasCopyDiff ? (
            <p className="panel__muted">No string-heavy output fields changed for this action.</p>
          ) : null}
          {diff.copyDiffVsPreviousAction.length > 0 ? (
            <div className="agent-copy-diff-block">
              <strong>vs previous action</strong>
              {diff.copyDiffVsPreviousAction.map((entry) => (
                <CopyDiffLines
                  key={`prev-${entry.key}`}
                  keyPrefix="prev"
                  entry={entry}
                  hideUnchangedDiffLines={hideUnchangedDiffLines}
                />
              ))}
            </div>
          ) : null}
          {diff.copyDiffVsPreviousCapability.length > 0 ? (
            <div className="agent-copy-diff-block">
              <strong>vs previous same capability</strong>
              {diff.copyDiffVsPreviousCapability.map((entry) => (
                <CopyDiffLines
                  key={`cap-${entry.key}`}
                  keyPrefix="cap"
                  entry={entry}
                  hideUnchangedDiffLines={hideUnchangedDiffLines}
                />
              ))}
            </div>
          ) : null}
        </div>
        <div className="drawer__footer">
          <button className="button button--ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
