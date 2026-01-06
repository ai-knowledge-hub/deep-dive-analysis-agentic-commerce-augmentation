"use client";

import type { Product } from "../../lib/types";

type Props = {
  products?: Product[];
};

export function ProductReasoning({ products }: Props) {
  if (!products || products.length === 0) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="text-lg font-semibold text-slate-100">Empowerment Reasoning</h2>
        <p className="text-sm text-slate-400">No recommendations yet.</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Empowerment Reasoning</h2>
      {products.map((product) => (
        <article key={product.id} className="space-y-2 rounded-lg bg-slate-900/80 p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="font-semibold">{product.name}</div>
            {product.confidence !== undefined && (
              <span className="text-xs text-emerald-300">Confidence: {(product.confidence * 100).toFixed(0)}%</span>
            )}
          </div>
          {product.capabilities_enabled && product.capabilities_enabled.length > 0 && (
            <div className="text-xs text-slate-400">
              Capabilities: {product.capabilities_enabled.join(", ")}
            </div>
          )}
          <p className="text-sm text-slate-100 whitespace-pre-wrap">
            {product.reasoning || "No reasoning provided."}
          </p>
        </article>
      ))}
    </section>
  );
}
