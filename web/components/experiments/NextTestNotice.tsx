import type { NextTestRecommendation } from "../../lib/types";
import { MLPrediction } from "./MLPrediction";
import { ThompsonSamplingGauge } from "./ThompsonSamplingGauge";

type NextTestNoticeProps = {
  nextTest: NextTestRecommendation | null;
  canRunVariantTests: boolean;
  runningVariantId: string | null;
  isSubmitting: boolean;
  isCreatingSuggestedVariant: boolean;
  onRunRecommended: () => void;
  onCreateSuggestedVariant: () => void;
};

export function NextTestNotice({
  nextTest,
  canRunVariantTests,
  runningVariantId,
  isSubmitting,
  isCreatingSuggestedVariant,
  onRunRecommended,
  onCreateSuggestedVariant,
}: NextTestNoticeProps) {
  if (!nextTest) return null;

  return (
    <div className="panel__notice panel__notice--info experiments-next-test">
      <strong>Next test:</strong> {nextTest.reason}
      {nextTest.action === "run_variant" && nextTest.variant_id ? (
        <div className="panel__actions">
          <button
            type="button"
            className="panel__action"
            onClick={onRunRecommended}
            disabled={runningVariantId === nextTest.variant_id || !canRunVariantTests}
          >
            {runningVariantId === nextTest.variant_id ? "Running…" : "Run recommended"}
          </button>
        </div>
      ) : null}
      {nextTest.action === "create_variant" ? (
        <div className="panel__actions">
          <button
            type="button"
            className="panel__action"
            onClick={onCreateSuggestedVariant}
            disabled={isSubmitting}
          >
            {isCreatingSuggestedVariant ? (
              <>
                Creating variant<span className="button__dots" />
              </>
            ) : (
              "Create suggested variant"
            )}
          </button>
        </div>
      ) : null}
      {nextTest.ml_prediction ? (
        <div className="panel__meta panel__meta--stack">
          <MLPrediction prediction={nextTest.ml_prediction} />
        </div>
      ) : null}
      {typeof nextTest.exploration_score === "number" &&
      typeof nextTest.exploitation_score === "number" ? (
        <div className="panel__meta panel__meta--stack">
          <ThompsonSamplingGauge
            explorationScore={nextTest.exploration_score}
            exploitationScore={nextTest.exploitation_score}
          />
        </div>
      ) : null}
    </div>
  );
}
