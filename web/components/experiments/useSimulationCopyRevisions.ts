"use client";

import { useEffect, useState } from "react";
import type { CopyRevision } from "../../lib/types";
import { listCopyRevisions } from "../../lib/api";

export function useSimulationCopyRevisions({
  productId,
  userId,
}: {
  productId?: string | null;
  userId: string | null;
}) {
  const [simulationRevisions, setSimulationRevisions] = useState<CopyRevision[]>([]);
  const [selectedSimulationRevisionId, setSelectedSimulationRevisionId] = useState("");
  const [simulationRevisionStatus, setSimulationRevisionStatus] = useState<
    string | null
  >(null);

  useEffect(() => {
    if (!productId) {
      setSimulationRevisions([]);
      setSelectedSimulationRevisionId("");
      return;
    }
    let cancelled = false;
    void listCopyRevisions({
      product_id: productId,
      source_type: "simulation",
      user_id: userId,
      limit: 50,
    })
      .then((response) => {
        if (cancelled) return;
        const revisions = response.revisions ?? [];
        setSimulationRevisions(revisions);
        setSelectedSimulationRevisionId((current) => {
          if (current && revisions.some((item) => item.id === current)) return current;
          return revisions[0]?.id ?? "";
        });
      })
      .catch(() => {
        if (cancelled) return;
        setSimulationRevisions([]);
        setSelectedSimulationRevisionId("");
      });
    return () => {
      cancelled = true;
    };
  }, [productId, userId]);

  return {
    simulationRevisions,
    selectedSimulationRevisionId,
    setSelectedSimulationRevisionId,
    simulationRevisionStatus,
    setSimulationRevisionStatus,
  };
}
