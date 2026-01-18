import type { ConversationResponse } from "../../lib/types";

type Props = {
  intent?: ConversationResponse["intent"];
};

export function IntentDisplay({ intent }: Props) {
  if (!intent?.label) return null;
  const confidence =
    intent.confidence !== undefined ? (intent.confidence * 100).toFixed(0) : "—";
  return (
    <div className="intent-card">
      <div className="intent-card__title">Inferred Intent</div>
      <div className="intent-card__label">{intent.label}</div>
      <div className="intent-card__meta">Confidence: {confidence}%</div>
    </div>
  );
}
