"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  EvidenceAnalyzeResponse,
  SessionSummary,
  SimulationRunSummary,
  Experiment,
} from "../../lib/types";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { EvidencePanel } from "../../components/evidence/EvidencePanel";
import {
  deleteConversationSession,
  deleteExperiment,
  deleteSimulationRun,
  extractEvidenceSignals,
  getConversationSnapshot,
  listConversationSessions,
  listProductsByBrand,
  listSimulationRuns,
  listExperiments,
} from "../../lib/api";
import { useTenant } from "../../components/tenant/TenantProvider";
import { buildExperimentHref, buildSimulationHref } from "../../lib/routes";

export default function EvidencePage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const { clientId, productId, productName, brandId } = useTenant();
  const storageClientId =
    clientId ??
    (typeof window !== "undefined"
      ? window.localStorage.getItem("client_id")
      : null) ??
    undefined;
  const storageKey = useMemo(() => {
    const clientTag = storageClientId ? `.${storageClientId}` : "";
    return userId
      ? `intentionality.evidence.${userId}${clientTag}`
      : `intentionality.evidence.anonymous${clientTag}`;
  }, [storageClientId, userId]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [analysis, setAnalysis] = useState<EvidenceAnalyzeResponse | null>(null);
  const [signalExtraction, setSignalExtraction] = useState<
    EvidenceAnalyzeResponse["signal_extraction"] | null
  >(null);
  const [optimization, setOptimization] = useState<null>(null);
  const [verification, setVerification] = useState<null>(null);
  const [targetCopy, setTargetCopy] = useState<string | null>(null);
  const [targetCopyUrl, setTargetCopyUrl] = useState<string | null>(null);
  const [evidenceSourceSessionId, setEvidenceSourceSessionId] = useState<string | null>(
    null,
  );
  const [evidenceRefreshedAt, setEvidenceRefreshedAt] = useState<string | null>(null);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = localStorage.getItem(storageKey);
    if (!raw) return;
    try {
      const payload = JSON.parse(raw) as Record<string, unknown>;
      setAnalysis((payload.analysis as EvidenceAnalyzeResponse) ?? null);
      setSignalExtraction((payload.signal_extraction as EvidenceAnalyzeResponse["signal_extraction"]) ?? null);
      setEvidenceSourceSessionId((payload.source_session_id as string) ?? null);
      setEvidenceRefreshedAt((payload.refreshed_at as string) ?? null);
      setOptimization(null);
      setVerification(null);
    } catch {
      localStorage.removeItem(storageKey);
    }
  }, [storageKey]);

  useEffect(() => {
    if (!userId || analysis) return;
    const loadFromLatestSession = async () => {
      try {
        const response = await listConversationSessions(userId);
        const sorted = [...(response.sessions ?? [])].sort((a, b) => {
          const aTime = new Date(a.last_turn_at ?? a.created_at ?? 0).getTime();
          const bTime = new Date(b.last_turn_at ?? b.created_at ?? 0).getTime();
          return bTime - aTime;
        });
        const latest = sorted[0];
        if (!latest?.id) return;
        const snapshot = await getConversationSnapshot(latest.id, userId);
        const research =
          snapshot.plan?.research_results ?? snapshot.plan?.products ?? [];
        if (!research.length) return;
        const evidenceProducts = research.map((item) => ({
          id: item.id ?? item.name,
          name: item.name,
          description: item.description ?? item.name,
          source: item.source ?? "research",
          url: item.offer_url,
          price: item.price,
          confidence: item.confidence,
          metadata: {
            alignment_score: item.alignment_score,
            alignment_reasoning: item.alignment_reasoning,
          },
        }));
        const alignmentScores =
          snapshot.plan?.alignment?.research?.per_item?.map((score) => ({
            product_id: score.product_id ?? "",
            score: score.score ?? 0,
            alignment_reasoning: score.alignment_reasoning,
          })) ?? [];
        const goals = snapshot.goal_state?.extracted_goals ?? [];
        const inferred = snapshot.intentionality_profiles ?? [];
        const nextAnalysis: EvidenceAnalyzeResponse = {
          intent: snapshot.intent,
          goals,
          evidence_products: evidenceProducts,
          profiles: inferred,
          alignment_scores: alignmentScores,
        };
        setAnalysis(nextAnalysis);
        setSignalExtraction(null);
        setEvidenceSourceSessionId(latest.id);
        const refreshedAt = new Date().toISOString();
        setEvidenceRefreshedAt(refreshedAt);
        localStorage.setItem(
          storageKey,
          JSON.stringify({
            analysis: nextAnalysis,
            signal_extraction: null,
            source_session_id: latest.id,
            refreshed_at: refreshedAt,
          }),
        );
      } catch (error) {
        console.warn("Failed to hydrate evidence from latest session", error);
      }
    };
    void loadFromLatestSession();
  }, [analysis, storageKey, userId]);

  useEffect(() => {
    if (!analysis || !targetCopy) return;
    const goal =
      analysis.intent?.primary_goal ??
      analysis.goals?.[0] ??
      "";
    if (!goal) return;
    const scores = analysis.alignment_scores ?? [];
    const topScore = [...scores].sort(
      (a, b) => (b.score ?? 0) - (a.score ?? 0),
    )[0];
    const winner =
      topScore &&
      analysis.evidence_products?.find(
        (item) => item.id === topScore.product_id,
      );
    void extractEvidenceSignals(
      {
        goal,
        product: {
          id: productId ?? undefined,
          name: productName ?? undefined,
          description: targetCopy ?? undefined,
        },
        winner: winner
          ? {
              id: winner.id,
              name: winner.name,
              description: winner.description ?? winner.raw_text ?? "",
            }
          : undefined,
      },
      userId,
    )
      .then((response) => {
        setSignalExtraction(response.signals ?? null);
        if (typeof window !== "undefined") {
          const refreshedAt = new Date().toISOString();
          setEvidenceRefreshedAt(refreshedAt);
          localStorage.setItem(
            storageKey,
            JSON.stringify({
              analysis,
              signal_extraction: response.signals ?? null,
              source_session_id: evidenceSourceSessionId,
              refreshed_at: refreshedAt,
            }),
          );
        }
      })
      .catch((error) => {
        console.warn("Failed to extract evidence signals", error);
      });
  }, [
    analysis,
    evidenceSourceSessionId,
    productId,
    productName,
    storageKey,
    targetCopy,
    userId,
  ]);

  useEffect(() => {
    if (!brandId || !productId || !userId) return;
    const loadTargetCopy = async () => {
      try {
        const response = await listProductsByBrand(brandId, userId);
        const product = response.products?.find((item) => item.id === productId);
        if (!product) return;
        const metadata = (product.metadata ?? {}) as Record<string, unknown>;
        const creative = (metadata.creative ?? {}) as Record<string, unknown>;
        const copy =
          (creative.manual_copy as string | undefined) ??
          (creative.imported_copy as string | undefined) ??
          product.description ??
          null;
        const url =
          (creative.source_url as string | undefined) ??
          (metadata.source_url as string | undefined) ??
          null;
        setTargetCopy(copy);
        setTargetCopyUrl(url);
      } catch (error) {
        console.warn("Failed to load target product copy", error);
      }
    };
    void loadTargetCopy();
  }, [brandId, productId, userId]);

  useEffect(() => {
    if (!userId) return;
    void listConversationSessions(userId).then((response) => {
      setSessions(response.sessions ?? []);
    });
    void listSimulationRuns(userId).then((response) => {
      setSimulationRuns(response.runs ?? []);
    });
    void listExperiments(userId).then((response) => {
      setExperiments(response.experiments ?? []);
    });
  }, [userId, clientId]);

  const handleCloseHistory = useCallback(() => {
    if (isHistoryClosing) return;
    setHistoryClosing(true);
    window.setTimeout(() => {
      setHistoryOpen(false);
      setHistoryClosing(false);
    }, 200);
  }, [isHistoryClosing]);

  const handleDeleteSimulationRun = useCallback(
    async (runId: string) => {
      if (!userId) return;
      try {
        await deleteSimulationRun(runId, userId, clientId ?? undefined);
        setSimulationRuns((current) => current.filter((run) => run.id !== runId));
      } catch {
        // ignore delete errors
      }
    },
    [clientId, userId],
  );

  const handleDeleteExperiment = useCallback(
    async (experimentId: string) => {
      if (!userId) return;
      try {
        await deleteExperiment(experimentId, userId, clientId ?? undefined);
        setExperiments((current) =>
          current.filter((experiment) => experiment.id !== experimentId),
        );
      } catch {
        // ignore delete errors
      }
    },
    [clientId, userId],
  );

  const confirmDeleteSession = useCallback(async () => {
    if (!deleteTargetId) return;
    try {
      await deleteConversationSession(deleteTargetId, userId);
      setSessions((current) => current.filter((item) => item.id !== deleteTargetId));
    } finally {
      setDeleteTargetId(null);
    }
  }, [deleteTargetId, userId]);

  const handleBulkDeleteSessions = useCallback(
    async (sessionIds: string[]) => {
      if (!sessionIds.length || !userId) return;
      const ok = window.confirm(
        `Delete ${sessionIds.length} chat session${sessionIds.length === 1 ? "" : "s"}?`,
      );
      if (!ok) return;
      await Promise.all(
        sessionIds.map((id) =>
          deleteConversationSession(id, userId).catch(() => null),
        ),
      );
      setSessions((current) => current.filter((item) => !sessionIds.includes(item.id)));
      setDeleteTargetId(null);
    },
    [userId],
  );

  const handleBulkDeleteSimulations = useCallback(
    async (runIds: string[]) => {
      if (!runIds.length || !userId) return;
      const ok = window.confirm(
        `Delete ${runIds.length} simulation run${runIds.length === 1 ? "" : "s"}?`,
      );
      if (!ok) return;
      await Promise.all(
        runIds.map((id) =>
          deleteSimulationRun(id, userId, clientId ?? undefined).catch(() => null),
        ),
      );
      setSimulationRuns((current) => current.filter((run) => !runIds.includes(run.id)));
    },
    [clientId, userId],
  );

  const handleBulkDeleteExperiments = useCallback(
    async (experimentIds: string[]) => {
      if (!experimentIds.length || !userId) return;
      const ok = window.confirm(
        `Delete ${experimentIds.length} experiment${experimentIds.length === 1 ? "" : "s"}?`,
      );
      if (!ok) return;
      await Promise.all(
        experimentIds.map((id) =>
          deleteExperiment(id, userId, clientId ?? undefined).catch(() => null),
        ),
      );
      setExperiments((current) =>
        current.filter((experiment) => !experimentIds.includes(experiment.id)),
      );
    },
    [clientId, userId],
  );

  return (
    <div className="app">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/lab")}
        sessions={sessions}
        activeSessionId={null}
        onSelectSession={(sessionId) => router.push(`/?session=${sessionId}`)}
        onDeleteSession={(sessionId) => setDeleteTargetId(sessionId)}
        onOpenHistory={() => {
          setHistoryOpen(true);
          setHistoryClosing(false);
        }}
      />
      {isSidebarOpen && (
        <button
          type="button"
          className="sidebar-overlay is-visible"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close menu"
        />
      )}
      {deleteTargetId && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal">
            <h4>Delete conversation?</h4>
            <p>This will permanently remove the chat history.</p>
            <div className="modal__actions">
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setDeleteTargetId(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button button--primary"
                onClick={confirmDeleteSession}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
      <HistoryDrawer
        isOpen={isHistoryOpen}
        isClosing={isHistoryClosing}
        sessions={sessions}
        simulations={simulationRuns}
        experiments={experiments}
        activeSessionId={null}
        onClose={handleCloseHistory}
        onSelect={(session) => {
          router.push(`/?session=${session.id}`);
          handleCloseHistory();
        }}
        onSelectSimulation={(run) => {
          router.push(buildSimulationHref(run.id));
          handleCloseHistory();
        }}
        onSelectExperiment={(experiment) => {
          router.push(buildExperimentHref(experiment.id));
          handleCloseHistory();
        }}
        onRequestDelete={(sessionId) => setDeleteTargetId(sessionId)}
        onRequestDeleteSimulation={handleDeleteSimulationRun}
        onRequestDeleteExperiment={handleDeleteExperiment}
        onRequestDeleteSessionsBulk={handleBulkDeleteSessions}
        onRequestDeleteSimulationsBulk={handleBulkDeleteSimulations}
        onRequestDeleteExperimentsBulk={handleBulkDeleteExperiments}
      />
      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Evidence Discovery"
            subtitle="Review the latest evidence analysis and optimized representation."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/lab")}
          />
          <EvidencePanel
            analysis={analysis}
            signalExtraction={signalExtraction ?? undefined}
            targetProductId={productId ?? undefined}
            targetProductName={productName ?? undefined}
            targetProductCopy={targetCopy ?? undefined}
            targetProductUrl={targetCopyUrl ?? undefined}
            sourceSessionId={evidenceSourceSessionId ?? undefined}
            refreshedAt={evidenceRefreshedAt ?? undefined}
            onOpenSimulation={() => router.push("/simulation")}
            onOpenExperiments={() => router.push("/experiments")}
            usePageScroll
          />
          <div className="detail__note">
            Evidence runs sync from the latest chat query. Run a new query to
            refresh.
          </div>
        </div>
      </main>
    </div>
  );
}
