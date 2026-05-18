"use client";

import { useEffect, useState } from "react";
import {
  listBatteries,
  listConversationSessions,
  listExperiments,
  listSimulationRuns,
} from "../../lib/api";
import type { Experiment, QueryBattery, SessionSummary, SimulationRunSummary } from "../../lib/types";

export function useExperimentInitialLists({
  userId,
  clientId,
  productId,
  selectedExperimentId,
}: {
  userId: string | null;
  clientId?: string | null;
  productId?: string | null;
  selectedExperimentId: string | null;
}) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [batteries, setBatteries] = useState<QueryBattery[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);

  useEffect(() => {
    if (!userId) return;
    void listConversationSessions(userId).then((response) => {
      setSessions(response.sessions ?? []);
    });
    void listSimulationRuns(userId).then((response) => {
      setSimulationRuns(response.runs ?? []);
    });
  }, [clientId, userId]);

  useEffect(() => {
    void listBatteries(userId, productId ?? undefined).then((response) => {
      setBatteries(response.batteries ?? []);
    });
    void listExperiments(userId, productId ?? undefined).then((response) => {
      setExperiments(response.experiments ?? []);
    });
  }, [productId, selectedExperimentId, userId]);

  return {
    sessions,
    setSessions,
    simulationRuns,
    setSimulationRuns,
    batteries,
    setBatteries,
    experiments,
    setExperiments,
  };
}
