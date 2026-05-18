"use client";

import { useEffect, useState } from "react";
import { listExperimentMetrics, listExperimentVariants } from "../../lib/api";
import type { Experiment } from "../../lib/types";

type ExperimentSnapshot = {
  winnerLabel?: string;
  winRate?: number | null;
  measuredAt?: string | null;
};

export function useExperimentSnapshots(
  experiments: Experiment[],
  userId: string | null,
): Record<string, ExperimentSnapshot> {
  const [snapshots, setSnapshots] = useState<Record<string, ExperimentSnapshot>>({});

  useEffect(() => {
    if (!userId || experiments.length === 0) {
      setSnapshots({});
      return;
    }
    let active = true;
    void (async () => {
      const entries = await Promise.all(
        experiments.map(async (experiment) => {
          try {
            const [metricsResponse, variantsResponse] = await Promise.all([
              listExperimentMetrics(experiment.id, userId),
              listExperimentVariants(experiment.id, userId),
            ]);
            const metricsList = metricsResponse.metrics ?? [];
            const variantsList = variantsResponse.variants ?? [];
            const variantLabelById = new Map(
              variantsList.map((variant) => [variant.id, variant.label]),
            );
            let bestVariantId: string | null = null;
            let bestWinRate = -1;
            let measuredAt: string | null = null;
            metricsList.forEach((metric) => {
              const rawWinRate = Number((metric.metrics ?? {}).win_rate);
              if (!Number.isFinite(rawWinRate)) return;
              if (rawWinRate > bestWinRate) {
                bestWinRate = rawWinRate;
                bestVariantId = metric.variant_id ?? null;
                measuredAt = metric.created_at ?? null;
              } else if (
                rawWinRate === bestWinRate &&
                (metric.created_at ?? "") > (measuredAt ?? "")
              ) {
                bestVariantId = metric.variant_id ?? null;
                measuredAt = metric.created_at ?? null;
              }
            });
            return [
              experiment.id,
              {
                winnerLabel: bestVariantId
                  ? variantLabelById.get(bestVariantId) ?? bestVariantId
                  : undefined,
                winRate: bestWinRate >= 0 ? bestWinRate : null,
                measuredAt,
              },
            ] as const;
          } catch {
            return [experiment.id, {}] as const;
          }
        }),
      );
      if (!active) return;
      setSnapshots(Object.fromEntries(entries));
    })();
    return () => {
      active = false;
    };
  }, [experiments, userId]);

  return snapshots;
}
