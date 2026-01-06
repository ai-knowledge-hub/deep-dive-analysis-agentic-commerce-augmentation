"use client";

type Props = {
  clarifications: string[];
  empowermentScore?: number;
};

export function WorldAvsB({ clarifications, empowermentScore }: Props) {
  return (
    <section className="grid gap-4 md:grid-cols-2">
      <div className="rounded-xl border border-red-900/60 bg-red-900/20 p-4">
        <h2 className="text-lg font-semibold text-red-200">World A (Extraction)</h2>
        <p className="text-sm text-red-100">
          High-pressure funnels push urgency, scarcity, and opacity. We show this column as a reminder of the
          status quo we are replacing.
        </p>
      </div>
      <div className="rounded-xl border border-emerald-700 bg-emerald-900/20 p-4 space-y-3">
        <h2 className="text-lg font-semibold text-emerald-200">World B (Empowerment)</h2>
        <p className="text-sm text-emerald-100">
          Clarifications and constraints drive every action. Empowerment Score:{" "}
          <strong>{Math.round((empowermentScore ?? 0) * 100)}%</strong>
        </p>
        <ul className="list-disc space-y-1 pl-5 text-sm text-emerald-100">
          {clarifications.length > 0 ? (
            clarifications.map((item, idx) => <li key={idx}>{item}</li>)
          ) : (
            <li>No clarifications issued in this turn.</li>
          )}
        </ul>
      </div>
    </section>
  );
}
