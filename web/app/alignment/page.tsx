"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  ConversationResponse,
  SessionSummary,
  SimulationRunSummary,
  Experiment,
} from "../../lib/types";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { IntentDisplay } from "../../components/intent/IntentDisplay";
import { IntentionalityProfileCard } from "../../components/products/IntentionalityProfileCard";
import { GoalClarificationPanel } from "../../components/values/GoalClarificationPanel";
import { ProductReasoning } from "../../components/products/ProductReasoning";
import { useTenant } from "../../components/tenant/TenantProvider";
import {
  createBattery,
  deleteConversationSession,
  deleteExperiment,
  deleteSimulationRun,
  listConversationSessions,
  listSimulationRuns,
  listExperiments,
} from "../../lib/api";

type AlignmentSnapshot = {
  intent?: ConversationResponse["intent"];
  goal_state?: ConversationResponse["goal_state"];
  plan?: ConversationResponse["plan"];
  clarifications?: string[];
  product_reasoning?: ConversationResponse["product_explanations"];
  research_results?: ConversationResponse["plan"]["research_results"];
  last_query?: string | null;
};

export default function AlignmentPage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const storageKey = useMemo(
    () => (userId ? `intentionality.alignment.${userId}` : "intentionality.alignment.anonymous"),
    [userId],
  );
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [snapshot, setSnapshot] = useState<AlignmentSnapshot>({});
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [batteryStatus, setBatteryStatus] = useState<string | null>(null);
  const { brandId, brandName, productName, clientId } = useTenant();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = localStorage.getItem(storageKey);
    if (!raw) return;
    try {
      setSnapshot(JSON.parse(raw) as AlignmentSnapshot);
    } catch {
      localStorage.removeItem(storageKey);
    }
  }, [storageKey]);

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

  const handleQuickCreateBattery = useCallback(
    async (productId: string, productName?: string) => {
      if (!productId) return;
      const name = productName ? `${productName} Battery` : "Product Battery";
      try {
        await createBattery({
          name,
          product_id: productId,
          brand_id: brandId ?? undefined,
          generation_mode: "bottom_up",
          user_id: userId,
        });
        setBatteryStatus(`Battery created for ${productName ?? "product"}.`);
        window.setTimeout(() => setBatteryStatus(null), 4000);
      } catch (error) {
        setBatteryStatus(
          error instanceof Error ? error.message : "Unable to create battery.",
        );
      }
    },
    [brandId, userId],
  );

  const plan = snapshot.plan;
  const products = plan?.products ?? [];
  const research = snapshot.research_results ?? plan?.research_results ?? [];
  const normalizedBrand = useMemo(
    () => (brandName ? brandName.toLowerCase().trim() : ""),
    [brandName],
  );
  const normalizedProduct = useMemo(
    () => (productName ? productName.toLowerCase().trim() : ""),
    [productName],
  );
  const matchedResearch = useMemo(() => {
    if (!research.length) return null;
    const clean = (value?: string) =>
      value
        ? value
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, " ")
            .trim()
        : "";
    return (
      research.find((item) => {
        const name = clean(item.name);
        const merchant = clean(item.merchant_name);
        const byProduct =
          normalizedProduct && name.includes(clean(normalizedProduct));
        const byBrand =
          normalizedBrand &&
          (name.includes(clean(normalizedBrand)) ||
            merchant.includes(clean(normalizedBrand)));
        return Boolean(byProduct || byBrand);
      }) ?? null
    );
  }, [normalizedBrand, normalizedProduct, research]);

  return (
    <div className="app">
      <Sidebar
        mobileOpen={isSidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        onNewConversation={() => router.push("/")}
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
          router.push(`/simulation?run_id=${run.id}`);
          handleCloseHistory();
        }}
        onSelectExperiment={(experiment) => {
          router.push(`/experiments?experiment_id=${experiment.id}`);
          handleCloseHistory();
        }}
        onRequestDelete={(sessionId) => setDeleteTargetId(sessionId)}
        onRequestDeleteSimulation={handleDeleteSimulationRun}
        onRequestDeleteExperiment={handleDeleteExperiment}
      />
      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Alignment Overview"
            subtitle="Review inferred intent, clarifications, and alignment results."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/")}
          />

          <div className="detail__stack">
            <IntentDisplay intent={snapshot.intent} />
            <IntentionalityProfileCard
              product={products?.[0]}
              alignmentScore={plan?.alignment?.goal_alignment?.score}
              baselineScore={plan?.alignment?.goal_alignment?.baseline_score}
            />
            <GoalClarificationPanel state={snapshot.goal_state} />
          </div>

          <div className="detail__grid">
            <div className="profile-card">
              <div className="profile-card__title">Brand Presence</div>
              {!brandName && !productName ? (
                <p className="profile-card__value">
                  Select a brand or product to check whether it appears in the
                  research results.
                </p>
              ) : matchedResearch ? (
                <>
                  <p className="profile-card__value">
                    ✅ Your{" "}
                    {productName ? "product" : "brand"} appears in the research
                    results.
                  </p>
                  <p className="profile-card__hint">
                    Matched: {matchedResearch.name}
                  </p>
                </>
              ) : (
                <>
                  <p className="profile-card__value">
                    Your {productName ? "product" : "brand"} did not appear in
                    the research results.
                  </p>
                  <p className="profile-card__hint">
                    Run a simulation to improve copy + ACP/UCP readiness so the
                    product surfaces in real‑world discovery.
                  </p>
                  <button
                    type="button"
                    className="button button--primary"
                    onClick={() => router.push("/simulation")}
                  >
                    Open Simulation
                  </button>
                </>
              )}
            </div>
            <div id="alignment-research">
              <ProductReasoning
                title="Research insights"
                products={research}
                badge="Research"
                disclaimer="Research insights are synthesized from external sources; verify before purchase."
                onQuickCreateBattery={handleQuickCreateBattery}
                statusMessage={batteryStatus}
              />
            </div>
          </div>

          <div className="detail__note">
            Alignment data reflects the latest chat session. Ask a new question
            to update.
          </div>
        </div>
      </main>
    </div>
  );
}
