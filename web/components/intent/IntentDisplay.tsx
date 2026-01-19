import type { ConversationResponse } from "../../lib/types";

type Props = {
  intent?: ConversationResponse["intent"];
};

export function IntentDisplay({ intent }: Props) {
  if (!intent?.primary_goal) return null;
  const confidence =
    intent.confidence !== undefined ? (intent.confidence * 100).toFixed(0) : "—";
  return (
    <div className="intent-card">
      <div className="intent-card__title">Inferred Intent</div>
      <div className="intent-card__label">{intent.primary_goal}</div>
      {intent.secondary_goals?.length ? (
        <div className="intent-card__meta">
          Secondary: {intent.secondary_goals.slice(0, 2).join(", ")}
        </div>
      ) : null}
      {intent.underlying_needs?.length ? (
        <div className="intent-card__meta">
          Needs: {intent.underlying_needs.slice(0, 2).join(", ")}
        </div>
      ) : null}
      {intent.context_signals?.length ? (
        <div className="intent-card__meta">
          Signals: {intent.context_signals.slice(0, 2).join(", ")}
        </div>
      ) : null}
      <div className="intent-card__meta">Confidence: {confidence}%</div>
    </div>
  );
}
