"use client";

import { useEffect, useState } from "react";
import { listAgentRuns } from "../../lib/api";
import type { AgentRun } from "../../lib/types";

export function useLatestExperimentAgentRun(
  selectedExperimentId: string | null,
  userId: string | null,
): AgentRun | null {
  const [latestAgentRun, setLatestAgentRun] = useState<AgentRun | null>(null);

  useEffect(() => {
    if (!userId || !selectedExperimentId) {
      setLatestAgentRun(null);
      return;
    }
    void listAgentRuns(
      {
        experiment_id: selectedExperimentId,
        limit: 1,
      },
      userId,
    )
      .then((response) => {
        setLatestAgentRun((response.runs ?? [])[0] ?? null);
      })
      .catch(() => setLatestAgentRun(null));
  }, [selectedExperimentId, userId]);

  return latestAgentRun;
}
