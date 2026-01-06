"use client";

type Props = {
  clarifications: string[];
  empowermentScore?: number;
  worldAExample?: string;
};

export function WorldAvsB({ clarifications, empowermentScore, worldAExample }: Props) {
  const score = Math.round((empowermentScore ?? 0) * 100);
  const statusQuo = worldAExample?.trim();

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h3>World A vs B</h3>
        <span className="panel__badge">{score}%</span>
      </div>

      <div className="comparison">
        <div className="comparison__item comparison__item--a">
          <span className="comparison__label">World A</span>
          <p className="comparison__text">
            {statusQuo ?? "Baseline persuasion: urgency, scarcity, and opacity."}
          </p>
        </div>

        <div className="comparison__item comparison__item--b">
          <span className="comparison__label">World B</span>
          <p className="comparison__text">
            {clarifications.length > 0
              ? clarifications[0]
              : "Awaiting values clarification..."}
          </p>
        </div>
      </div>

      {clarifications.length > 1 && (
        <ul className="panel__list">
          {clarifications.slice(1).map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
