"use client";

import React from "react";
import type { ExperimentMetric, ExperimentVariant, NextTestRecommendation } from "../../lib/types";
import { ExperimentOutcomeReview } from "./ExperimentOutcomeReview";
import { ExperimentRunSettings } from "./ExperimentRunSettings";
import { ExperimentVariantRunItem } from "./ExperimentVariantRunItem";
import { NextTestNotice } from "./NextTestNotice";
import { OutcomeSnapshot } from "./OutcomeSnapshot";

type OutcomeSnapshotView = {
  runVariantLabel: string;
  runQueryLabel: string;
  runCreatedAt: string | null;
  winRate: string;
  avgScore: string;
  validationState: string;
  snapshotVersion: number | null;
};

type SignalCount = { signal: string; count: number };

type ExperimentGapSummary = {
  missing: SignalCount[];
  winner: SignalCount[];
  summaries: string[];
  total: number;
};

type Props = {
  labMode: "lab" | "manual";
  showManualControls: boolean;
  variants: ExperimentVariant[];
  metricsByVariant: Map<string, ExperimentMetric>;
  hypothesisLabelById: Map<string, string>;
  hypothesisStatementById: Map<string, Record<string, unknown>>;
  expandedHypothesisId: string | null;
  expandedVariantId: string | null;
  runningVariantId: string | null;
  canRunVariantTests: boolean;
  runMode: "simulation" | "retrieval_backed";
  retrievalMaxResults: string;
  currentProtocolSnapshotVersion: number | null;
  runVariantDisabledReason: string | null;
  nextTest: NextTestRecommendation | null;
  nextTestStatus: string | null;
  isSubmitting: boolean;
  isCreatingSuggestedVariant: boolean;
  outcomeSnapshot: OutcomeSnapshotView;
  hasValidationSignals: boolean;
  latestMetric: Record<string, unknown> | null;
  experimentGapSummary: ExperimentGapSummary | null;
  renderMetricValue: (value: unknown, fallback?: string) => string;
  resolveVariantDescription: (variant: ExperimentVariant) => string | null;
  onRunModeChange: (mode: "simulation" | "retrieval_backed") => void;
  onRetrievalMaxResultsChange: (value: string) => void;
  onToggleHypothesis: (hypothesisId: string | null) => void;
  onToggleCopy: (variantId: string) => void;
  onRunVariant: (variantId: string) => void;
  onRunRecommended: () => void;
  onCreateSuggestedVariant: () => void;
  onOpenValidation: () => void;
};

export function VariantRunPanel({
  labMode,
  showManualControls,
  variants,
  metricsByVariant,
  hypothesisLabelById,
  hypothesisStatementById,
  expandedHypothesisId,
  expandedVariantId,
  runningVariantId,
  canRunVariantTests,
  runMode,
  retrievalMaxResults,
  currentProtocolSnapshotVersion,
  runVariantDisabledReason,
  nextTest,
  nextTestStatus,
  isSubmitting,
  isCreatingSuggestedVariant,
  outcomeSnapshot,
  hasValidationSignals,
  latestMetric,
  experimentGapSummary,
  renderMetricValue,
  resolveVariantDescription,
  onRunModeChange,
  onRetrievalMaxResultsChange,
  onToggleHypothesis,
  onToggleCopy,
  onRunVariant,
  onRunRecommended,
  onCreateSuggestedVariant,
  onOpenValidation,
}: Props) {
  return (
    <>
      <p className="panel__subheading">Step 5 · Run experiment across battery queries</p>
      <p className="panel__step-helper">
        Retrieval-backed runs use the active evidence set to keep variant comparisons fair.
      </p>
      <ExperimentRunSettings
        runMode={runMode}
        retrievalMaxResults={retrievalMaxResults}
        currentProtocolSnapshotVersion={currentProtocolSnapshotVersion}
        runVariantDisabledReason={runVariantDisabledReason}
        onRunModeChange={onRunModeChange}
        onRetrievalMaxResultsChange={onRetrievalMaxResultsChange}
      />
      {variants.length === 0 ? (
        <p className="panel__empty">Add variants to run experiments.</p>
      ) : (
        <ul className="panel__list">
          {variants.map((variant) => {
            const resolvedDescription = resolveVariantDescription(variant);
            const hypothesisId = variant.hypothesis_id ?? null;
            const tested = metricsByVariant.has(variant.id);
            const metricValues = tested
              ? (((metricsByVariant.get(variant.id)?.metrics ?? {}) as Record<string, unknown>) ??
                null)
              : null;
            return (
              <li key={variant.id}>
                <ExperimentVariantRunItem
                  variant={variant}
                  tested={tested}
                  hypothesisLabel={
                    hypothesisId
                      ? hypothesisLabelById.get(hypothesisId) ?? "Linked test idea"
                      : "Linked test idea"
                  }
                  hypothesisStatement={
                    hypothesisId ? (hypothesisStatementById.get(hypothesisId) ?? null) : null
                  }
                  hypothesisExpanded={Boolean(hypothesisId) && expandedHypothesisId === hypothesisId}
                  copyExpanded={expandedVariantId === variant.id}
                  resolvedDescription={resolvedDescription}
                  metricValues={metricValues}
                  runButtonProminent={!(labMode === "lab" && !showManualControls)}
                  running={runningVariantId === variant.id}
                  canRun={canRunVariantTests}
                  renderMetricValue={renderMetricValue}
                  onToggleHypothesis={() => onToggleHypothesis(hypothesisId)}
                  onToggleCopy={() => onToggleCopy(variant.id)}
                  onRun={() => onRunVariant(variant.id)}
                />
              </li>
            );
          })}
        </ul>
      )}
      <NextTestNotice
        nextTest={nextTest}
        canRunVariantTests={canRunVariantTests}
        runningVariantId={runningVariantId}
        isSubmitting={isSubmitting}
        isCreatingSuggestedVariant={isCreatingSuggestedVariant}
        onRunRecommended={onRunRecommended}
        onCreateSuggestedVariant={onCreateSuggestedVariant}
      />
      {nextTestStatus ? <p className="panel__success">{nextTestStatus}</p> : null}
      <OutcomeSnapshot
        snapshot={outcomeSnapshot}
        hasValidationSignals={hasValidationSignals}
        onOpenValidation={onOpenValidation}
      />
      <ExperimentOutcomeReview
        latestMetric={latestMetric}
        experimentGapSummary={experimentGapSummary}
        renderMetricValue={renderMetricValue}
      />
    </>
  );
}
