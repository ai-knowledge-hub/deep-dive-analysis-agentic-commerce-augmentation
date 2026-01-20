"use client";

import type { GoalClarificationState } from "../../lib/types";

type Props = {
  state?: GoalClarificationState | null;
};

export function GoalClarificationPanel({ state }: Props) {
  return (
    <div className="panel__card">
      <div className="panel__header">
        <h3>Goal Clarification</h3>
        {state && (
          <span className="panel__badge panel__badge--secondary">
            {state.extracted_goals.length}
          </span>
        )}
      </div>

      {state ? (
        <>
          <p className="panel__subtitle">{state.query}</p>
          <ul className="panel__list">
            {state.extracted_goals.map((goal, idx) => (
              <li key={`${goal}-${idx}`}>{goal}</li>
            ))}
          </ul>
        </>
      ) : (
        <p className="panel__empty">No goals clarified yet.</p>
      )}
    </div>
  );
}
