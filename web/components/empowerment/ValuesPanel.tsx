"use client";

import type { ClarificationState } from "../../lib/types";

type Props = {
  state?: ClarificationState;
};

export function ValuesPanel({ state }: Props) {
  return (
    <section className="glass-card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Values Clarification</h2>
        {state?.ready_for_products ? (
          <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-300">
            Ready
          </span>
        ) : (
          <span className="rounded-full bg-yellow-500/20 px-3 py-1 text-xs font-semibold text-yellow-200">
            Clarifying
          </span>
        )}
      </div>
      {state ? (
        <>
          <p className="text-xs text-slate-400">Query: {state.query}</p>
          <ul className="list-disc space-y-2 pl-5 text-sm text-slate-100">
            {state.extracted_goals.length ? (
              state.extracted_goals.map((goal, idx) => <li key={idx}>{goal}</li>)
            ) : (
              <li className="text-slate-400">No goals extracted yet.</li>
            )}
          </ul>
        </>
      ) : (
        <p className="text-sm text-slate-400">Awaiting first clarification.</p>
      )}
    </section>
  );
}
