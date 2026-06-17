"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAppUser } from "../../lib/auth";

import { ControlPlaneBriefing } from "../../components/layout/ControlPlaneBriefing";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { Sidebar } from "../../components/layout/Sidebar";
import {
  buildCompensatingProposalCommand,
  compensatingProposalKey,
} from "../../components/agent/compensatingProposal";
import {
  ApprovalsSection,
  CommandWorkSection,
  EscalationsSection,
  PausesSection,
  RetriesSection,
} from "../../components/interventions/InterventionQueueSections";
import { InterventionStartGuide } from "../../components/interventions/InterventionStartGuide";
import {
  buildInterventionBriefing,
  buildInterventionMetrics,
} from "../../components/interventions/interventionBriefing";
import { formatActionLabel } from "../../components/interventions/interventionDisplay";
import {
  buildApprovalItems,
  buildCommandItems,
  buildDetails,
  buildEscalationItem,
  buildPauseItem,
  buildRetryItem,
  sortByPriorityAndRisk,
} from "../../components/interventions/interventionLogic";
import type {
  ApprovalItem,
  CommandItem,
  EscalationItem,
  PauseItem,
  RetryItem,
} from "../../components/interventions/interventionTypes";
import {
  controlAgentRun,
  decideAgentAction,
  getAgentRun,
  getAgentRunEvents,
  issueAgentRunCommand,
  listAgentRuns,
  listAgentRuntimeRegistry,
  preflightAgentRunCommand,
} from "../../lib/api";
import { buildRunsHref } from "../../lib/routes";
import type {
  AgentCompensatingAction,
  AgentRunCommandPreflight,
} from "../../lib/types";

function InterventionsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAppUser();
  const userId = user?.id ?? null;
  const runIdParam = searchParams.get("run_id")?.trim() || "";

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [retries, setRetries] = useState<RetryItem[]>([]);
  const [pauses, setPauses] = useState<PauseItem[]>([]);
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [commands, setCommands] = useState<CommandItem[]>([]);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [pendingCompensatingKey, setPendingCompensatingKey] = useState<string | null>(null);
  const [compensatingPreflights, setCompensatingPreflights] = useState<
    Record<string, AgentRunCommandPreflight>
  >({});

  const loadInterventions = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const [response, registry] = await Promise.all([
        listAgentRuns({ limit: 16 }, userId),
        listAgentRuntimeRegistry(userId).catch(() => null),
      ]);
      const nextRuns = response.runs ?? [];
      const harnessProfiles = registry?.harness_profiles ?? [];
      const detailRows = await Promise.all(
        nextRuns.map(async (run) => {
          try {
            const [detail, eventData] = await Promise.all([
              getAgentRun(run.id, { limit: 50 }, userId),
              getAgentRunEvents(run.id, { limit: 50, event_type: "all" }, userId),
            ]);
            return buildDetails(
              { ...run, ...(detail.run ?? {}) },
              detail.actions ?? [],
              eventData.events ?? [],
              harnessProfiles,
            );
          } catch {
            return buildDetails(run, [], [], harnessProfiles);
          }
        }),
      );

      setApprovals(
        sortByPriorityAndRisk(
          detailRows.flatMap((detail) => buildApprovalItems(detail)),
        ),
      );
      setRetries(
        sortByPriorityAndRisk(
          detailRows
            .map((detail) => buildRetryItem(detail))
            .filter((item): item is RetryItem => Boolean(item)),
        ),
      );
      setPauses(
        sortByPriorityAndRisk(
          detailRows
            .map((detail) => buildPauseItem(detail))
            .filter((item): item is PauseItem => Boolean(item)),
        ),
      );
      setEscalations(
        sortByPriorityAndRisk(
          detailRows
            .map((detail) => buildEscalationItem(detail))
            .filter((item): item is EscalationItem => Boolean(item)),
        ),
      );
      setCommands(
        sortByPriorityAndRisk(
          detailRows.flatMap((detail) => buildCommandItems(detail)),
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load interventions.");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void loadInterventions();
  }, [loadInterventions]);

  const visibleApprovals = useMemo(
    () => (runIdParam ? approvals.filter((item) => item.run.id === runIdParam) : approvals),
    [approvals, runIdParam],
  );

  const visibleRetries = useMemo(
    () => (runIdParam ? retries.filter((item) => item.run.id === runIdParam) : retries),
    [retries, runIdParam],
  );

  const visiblePauses = useMemo(
    () => (runIdParam ? pauses.filter((item) => item.run.id === runIdParam) : pauses),
    [pauses, runIdParam],
  );

  const visibleEscalations = useMemo(
    () => (runIdParam ? escalations.filter((item) => item.run.id === runIdParam) : escalations),
    [escalations, runIdParam],
  );

  const visibleCommands = useMemo(
    () => (runIdParam ? commands.filter((item) => item.run.id === runIdParam) : commands),
    [commands, runIdParam],
  );

  const briefing = useMemo(() => {
    return buildInterventionBriefing({
      userId,
      runIdParam,
      approvalsCount: visibleApprovals.length,
      commandsCount: visibleCommands.length,
      escalationsCount: visibleEscalations.length,
      pausesCount: visiblePauses.length,
      retriesCount: visibleRetries.length,
    });
  }, [
    runIdParam,
    userId,
    visibleApprovals.length,
    visibleCommands.length,
    visibleEscalations.length,
    visiblePauses.length,
    visibleRetries.length,
  ]);

  const handleDecision = useCallback(
    async (actionId: string, decision: "approve" | "reject") => {
      if (!userId) return;
      setBusyKey(`decision:${actionId}:${decision}`);
      setError(null);
      setStatusMessage(null);
      try {
        await decideAgentAction(actionId, { decision }, userId);
        setStatusMessage(
          decision === "approve"
            ? "Action approved. The queue has been refreshed."
            : "Action rejected. The queue has been refreshed.",
        );
        await loadInterventions();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to update action.");
      } finally {
        setBusyKey(null);
      }
    },
    [loadInterventions, userId],
  );

  const handleRunControl = useCallback(
    async (runId: string, action: "start" | "pause" | "cancel" | "step") => {
      if (!userId) return;
      setBusyKey(`control:${runId}:${action}`);
      setError(null);
      setStatusMessage(null);
      try {
        const response = await controlAgentRun(runId, action, userId);
        setStatusMessage(
          response.message ||
            (action === "pause"
              ? "Run paused and the queue has been refreshed."
              : action === "cancel"
                ? "Run canceled and the queue has been refreshed."
                : action === "start"
                  ? "Run resumed and the queue has been refreshed."
                  : "Run stepped forward and the queue has been refreshed."),
        );
        await loadInterventions();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to control run.");
      } finally {
        setBusyKey(null);
      }
    },
    [loadInterventions, userId],
  );

  const handleCompensatingAction = useCallback(
    async (item: CommandItem, recommendation: AgentCompensatingAction) => {
      if (!userId || !recommendation.capability_name) return;
      const busy = compensatingProposalKey(item.event.id, recommendation);
      if (!busy) return;
      const pendingKey = busy;
      const command = buildCompensatingProposalCommand(
        { event: item.event, experimentId: item.run.experiment_id },
        recommendation,
      );
      if (!command) return;
      setBusyKey(busy);
      setError(null);
      setStatusMessage(null);
      try {
        const response = await preflightAgentRunCommand(item.run.id, command, userId);
        setCompensatingPreflights((current) => ({
          ...current,
          [pendingKey]: response.preflight,
        }));
        if (!response.preflight.allowed) {
          setPendingCompensatingKey(null);
          return;
        }
        if (
          response.preflight.requires_confirmation &&
          pendingCompensatingKey !== pendingKey
        ) {
          setPendingCompensatingKey(pendingKey);
          return;
        }
        await issueAgentRunCommand(item.run.id, command, userId);
        setPendingCompensatingKey(null);
        setStatusMessage(
          `Recovery proposal created for ${formatActionLabel(recommendation.capability_name)}.`,
        );
        await loadInterventions();
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to create recovery proposal.",
        );
      } finally {
        setBusyKey(null);
      }
    },
    [loadInterventions, pendingCompensatingKey, userId],
  );

  function openRun(runId: string) {
    router.push(buildRunsHref({ runId }));
  }

  function openRuns() {
    router.push(buildRunsHref({ runId: runIdParam || null }));
  }

  return (
    <div className="app">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/lab")}
        sessions={[]}
        activeSessionId={null}
        onSelectSession={() => {}}
        onDeleteSession={() => {}}
        onOpenHistory={() => {}}
        showHistoryButton={false}
      />

      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Interventions"
            subtitle="Decision queue for approvals, retries, pauses, and manual escalation."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push(buildRunsHref({ runId: runIdParam || null }))}
            backLabel={runIdParam ? "Back to selected run" : "Open runs"}
            actions={
              <button
                type="button"
                className="button button--ghost"
                onClick={() => loadInterventions()}
                disabled={loading}
              >
                {loading ? "Refreshing..." : "Refresh"}
              </button>
            }
          />

          <ControlPlaneBriefing
            label="Decision"
            title="Intervention briefing"
            subtitle="Start with the top card. Counts are only there to size the queue."
            summary={briefing}
            metrics={buildInterventionMetrics({
              approvalsCount: approvals.length,
              commandsCount: commands.length,
              escalationsCount: escalations.length,
              pausesCount: pauses.length,
              retriesCount: retries.length,
            })}
            status={statusMessage}
            error={error}
          />

          {runIdParam ? (
            <section className="panel__notice panel__notice--info">
              <strong>Run-scoped view:</strong> showing intervention items for the selected run.
              <div className="panel__actions">
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => router.push(buildRunsHref({ runId: runIdParam }))}
                >
                  Return to run
                </button>
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => router.push("/interventions")}
                >
                  Clear run scope
                </button>
              </div>
            </section>
          ) : null}

          <section className="control-grid control-grid--compact control-grid--full">
            <InterventionStartGuide
              escalations={visibleEscalations}
              commands={visibleCommands}
              approvals={visibleApprovals}
              retries={visibleRetries}
              pauses={visiblePauses}
              busyKey={busyKey}
              onApprove={(actionId) => void handleDecision(actionId, "approve")}
              onOpenRun={openRun}
              onControlRun={(runId, action) => void handleRunControl(runId, action)}
              onOpenRuns={openRuns}
            />
            <EscalationsSection items={visibleEscalations} onOpenRun={openRun} />
            <CommandWorkSection
              items={visibleCommands}
              busyKey={busyKey}
              pendingCompensatingKey={pendingCompensatingKey}
              compensatingPreflights={compensatingPreflights}
              onCreateCompensatingAction={handleCompensatingAction}
              onOpenRun={openRun}
            />
            <ApprovalsSection
              items={visibleApprovals}
              busyKey={busyKey}
              onDecision={handleDecision}
              onOpenRun={openRun}
            />
            <RetriesSection
              items={visibleRetries}
              busyKey={busyKey}
              onRunControl={handleRunControl}
              onOpenRun={openRun}
            />
            <PausesSection
              items={visiblePauses}
              busyKey={busyKey}
              onRunControl={handleRunControl}
              onOpenRun={openRun}
            />
          </section>
        </div>
      </main>
    </div>
  );
}

export default function InterventionsPage() {
  return (
    <Suspense fallback={null}>
      <InterventionsPageContent />
    </Suspense>
  );
}
