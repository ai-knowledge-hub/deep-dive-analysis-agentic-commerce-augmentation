"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  SimulationLesson,
  SimulationOptimizeResponse,
  SimulationProduct,
  SimulationRetestResponse,
  SimulationRunResponse,
  SimulationRunSummary,
  SessionSummary,
  ConversationResponse,
} from "../../lib/types";
import {
  listSimulationLessons,
  listSimulationRuns,
  optimizeSimulation,
  retestSimulation,
  runSimulation,
  getSimulationRun,
  getConversationSnapshot,
  requestBrandTone,
  updateSimulationTone,
  listProductsByBrand,
  updateProductCopy,
  getBrand,
  attachSimulationProduct,
  listConversationSessions,
  deleteConversationSession,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { SimulationPanel } from "../../components/simulation/SimulationPanel";
import { SimulationHistory } from "../../components/simulation/SimulationHistory";
import { SimulationLessons } from "../../components/simulation/SimulationLessons";
import { useTenant } from "../../components/tenant/TenantProvider";

export default function SimulationPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const { productId, productName, brandId, setProductId } = useTenant();
  const storageKey = useMemo(
    () => (userId ? `intentionality.simulation.${userId}` : "intentionality.simulation.anonymous"),
    [userId],
  );
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [simulationScenario, setSimulationScenario] = useState("");
  const [simulationScenarioDirty, setSimulationScenarioDirty] = useState(false);
  const [simulationProducts, setSimulationProducts] = useState<SimulationProduct[]>([]);
  const [simulationRun, setSimulationRun] = useState<SimulationRunResponse | null>(null);
  const [simulationOptimized, setSimulationOptimized] =
    useState<SimulationOptimizeResponse | null>(null);
  const [simulationRetest, setSimulationRetest] =
    useState<SimulationRetestResponse | null>(null);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [simulationLessons, setSimulationLessons] = useState<SimulationLesson[]>([]);
  const [selectedSimulationProductId, setSelectedSimulationProductId] =
    useState<string | null>(null);
  const [simulationToneSuggestion, setSimulationToneSuggestion] = useState<string | null>(null);
  const [simulationTone, setSimulationTone] = useState("");
  const [simulationToneNotice, setSimulationToneNotice] = useState<string | null>(null);
  const [productCopy, setProductCopy] = useState("");
  const [productCopySaved, setProductCopySaved] = useState<string | null>(null);
  const [brandToneSummary, setBrandToneSummary] = useState<string | null>(null);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const keys = [
      storageKey,
      "intentionality.simulation.latest",
      "intentionality.simulation.anonymous",
    ];
    const raw = keys.map((key) => localStorage.getItem(key)).find(Boolean);
    if (!raw) return;
    try {
      const data = JSON.parse(raw) as Record<string, unknown>;
      setSimulationScenario((data.scenario as string) || "");
      setSimulationProducts((data.products as SimulationProduct[]) || []);
      setSimulationRun((data.run as SimulationRunResponse) || null);
      setSimulationOptimized((data.optimized as SimulationOptimizeResponse) || null);
      setSimulationRetest((data.retest as SimulationRetestResponse) || null);
      setSelectedSimulationProductId((data.selected_product_id as string) || null);
      setSimulationToneSuggestion((data.tone_suggestion as string) || null);
      setSimulationTone((data.tone as string) || "");
    } catch {
      localStorage.removeItem(storageKey);
    }
  }, [storageKey]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const payload = {
      scenario: simulationScenario,
      products: simulationProducts,
      run: simulationRun,
      optimized: simulationOptimized,
      retest: simulationRetest,
      selected_product_id: selectedSimulationProductId,
      tone_suggestion: simulationToneSuggestion,
      tone: simulationTone,
    };
    localStorage.setItem(storageKey, JSON.stringify(payload));
  }, [
    simulationOptimized,
    simulationProducts,
    simulationRetest,
    simulationRun,
    simulationScenario,
    simulationTone,
    simulationToneSuggestion,
    selectedSimulationProductId,
    storageKey,
  ]);

  useEffect(() => {
    void listSimulationRuns(userId).then((response) => {
      setSimulationRuns(response.runs ?? []);
    });
    void listSimulationLessons(userId).then((response) => {
      setSimulationLessons(response.lessons ?? []);
    });
    if (userId) {
      void listConversationSessions(userId).then((response) => {
        setSessions(response.sessions ?? []);
      });
    }
  }, [userId]);

  useEffect(() => {
    if (!brandId || simulationProducts.length > 0) return;
    let cancelled = false;
    void listProductsByBrand(brandId, userId).then((response) => {
      if (cancelled) return;
      const items = response.products ?? [];
      const mapped = items.map((product) => ({
        id: product.id,
        name: product.name,
        description: product.description ?? product.metadata?.description ?? product.name,
        source: "catalog",
        url: (product.metadata?.product_url as string | undefined) ?? undefined,
        price:
          typeof product.metadata?.price === "number"
            ? product.metadata?.price
            : undefined,
        confidence: 0.6,
        metadata: product.metadata ?? {},
      }));
      setSimulationProducts(mapped);
      if (mapped.length > 0) {
        const initial =
          productId && mapped.some((p) => p.id === productId)
            ? productId
            : mapped[0].id;
        setSelectedSimulationProductId(initial);
        setProductId(initial);
        const selected = mapped.find((item) => item.id === initial) ?? mapped[0];
        const creative = (selected?.metadata as Record<string, unknown> | undefined)?.creative as
          | Record<string, unknown>
          | undefined;
        setProductCopy(
          (creative?.manual_copy as string | undefined) ??
            selected?.description ??
            "",
        );
      }
    });
    return () => {
      cancelled = true;
    };
  }, [brandId, productId, setProductId, simulationProducts.length, userId]);

  useEffect(() => {
    if (!brandId) {
      setBrandToneSummary(null);
      return;
    }
    let cancelled = false;
    void getBrand(brandId, userId).then((response) => {
      if (cancelled) return;
      const tone = (response.brand?.metadata as Record<string, unknown> | undefined)?.tone as
        | Record<string, unknown>
        | undefined;
      setBrandToneSummary((tone?.summary as string | undefined) ?? null);
    });
    return () => {
      cancelled = true;
    };
  }, [brandId, userId]);

  useEffect(() => {
    if (!selectedSimulationProductId) return;
    const selected = simulationProducts.find(
      (item) => item.id === selectedSimulationProductId,
    );
    if (!selected) return;
    const creative = (selected.metadata as Record<string, unknown> | undefined)?.creative as
      | Record<string, unknown>
      | undefined;
    setProductCopy(
      (creative?.manual_copy as string | undefined) ??
        selected.description ??
        "",
    );
  }, [selectedSimulationProductId, simulationProducts]);

  useEffect(() => {
    const runIdParam = searchParams.get("run_id");
    if (!runIdParam) return;
    if (simulationRun?.run_id === runIdParam) return;
    let cancelled = false;
    void getSimulationRun(runIdParam, userId).then((response) => {
      if (cancelled) return;
      setSimulationRun({ run_id: response.run.id, result: response.run.result });
      setSimulationRetest(
        response.run.retest
          ? { run_id: response.run.id, result: response.run.retest }
          : null,
      );
      setSimulationOptimized(null);
      setSimulationScenario(response.run.query ?? "");
      setSimulationScenarioDirty(false);
      setSimulationProducts(response.run.products ?? []);
      if (response.run.product_id) {
        setSelectedSimulationProductId(response.run.product_id);
        setProductId(response.run.product_id);
      }
      setSimulationToneSuggestion(response.run.result?.tone?.summary ?? null);
      if (!simulationTone) {
        setSimulationTone(response.run.result?.tone?.summary ?? "");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [searchParams, setProductId, simulationRun?.run_id, simulationTone, userId]);

  useEffect(() => {
    const runIdParam = searchParams.get("run_id");
    if (runIdParam) return;
    const sessionParam = searchParams.get("session");
    if (!sessionParam) return;
    let cancelled = false;
    void getConversationSnapshot(sessionParam, userId).then((response) => {
      if (cancelled) return;
      const state = response.snapshot?.session?.state as
        | Record<string, unknown>
        | undefined;
      if (!state) return;
      const scenario = (state.last_query as string) ?? "";
      const products = (state.last_products as SimulationProduct[]) ?? [];
      setSimulationScenario(scenario);
      setSimulationScenarioDirty(false);
      setSimulationProducts(products);
      const selected =
        (state.last_product_id as string) ?? products[0]?.id ?? null;
      setSelectedSimulationProductId(selected);
      if (selected) {
        setProductId(selected);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [searchParams, setProductId, userId]);

  const handleRunSimulation = useCallback(async () => {
    if (!simulationScenario.trim()) return;
    if (simulationProducts.length === 0) return;
    setSimulationLoading(true);
    try {
      const response = await runSimulation(
        simulationScenario.trim(),
        simulationProducts,
        userId,
      );
      setSimulationRun(response);
      setSimulationOptimized(null);
      setSimulationRetest(null);
      setSimulationToneSuggestion(response.result?.tone?.summary ?? null);
      if (!simulationTone) {
        setSimulationTone(response.result?.tone?.summary ?? "");
      }
      void listSimulationLessons(userId).then((next) => {
        setSimulationLessons(next.lessons ?? []);
      });
      void listSimulationRuns(userId).then((next) => {
        setSimulationRuns(next.runs ?? []);
      });
    } finally {
      setSimulationLoading(false);
    }
  }, [simulationProducts, simulationScenario, simulationTone, userId]);

  const handleOptimizeSimulation = useCallback(
    async (productId?: string) => {
      const runId = simulationRun?.run_id;
      const gaps = simulationRun?.result?.gap_analysis ?? [];
      if (!runId || gaps.length === 0) return;
      const targetGap =
        (productId && gaps.find((gap) => gap.product_id === productId)) ||
        [...gaps].sort((a, b) => a.score - b.score)[0];
      setSimulationLoading(true);
      try {
        const response = await optimizeSimulation(
          runId,
          targetGap.product_id,
          simulationTone || undefined,
          userId,
        );
        setSimulationOptimized(response);
        setSelectedSimulationProductId(targetGap.product_id);
      } finally {
        setSimulationLoading(false);
      }
    },
    [simulationRun, simulationTone, userId],
  );

  const handleRetestSimulation = useCallback(async () => {
    if (!simulationRun || !simulationOptimized) return;
    const optimizedId = simulationOptimized.optimized.id;
    const updated = simulationProducts.map((product) =>
      product.id === optimizedId
        ? { ...product, description: simulationOptimized.optimized.after }
        : product,
    );
    setSimulationLoading(true);
    try {
      const response = await retestSimulation(simulationRun.run_id, updated, userId);
      setSimulationRetest(response);
    } finally {
      setSimulationLoading(false);
    }
  }, [simulationOptimized, simulationProducts, simulationRun, userId]);

  const handleSelectSimulationRun = useCallback(
    async (runId: string) => {
      const response = await getSimulationRun(runId, userId);
      const run = response.run;
      setSimulationRun({ run_id: run.id, result: run.result });
      setSimulationOptimized(null);
      setSimulationRetest(run.retest ? { run_id: run.id, result: run.retest } : null);
      setSimulationProducts(run.products ?? []);
      setSimulationScenario(run.query ?? "");
      setSimulationScenarioDirty(false);
      const scenario = (run.scenario as Record<string, unknown> | undefined) || {};
      const confirmedTone = (scenario.confirmed_tone as string | undefined) ?? "";
      const suggestedTone = (scenario.tone_suggestion as string | undefined) ?? null;
      setSimulationToneSuggestion(run.result?.tone?.summary ?? suggestedTone ?? null);
      setSimulationTone(confirmedTone || run.result?.tone?.summary || "");
      if (run.products?.length) {
        setSelectedSimulationProductId(run.products[0].id);
      }
    },
    [userId],
  );

  const handleOpenExperiments = useCallback(
    (_runId: string, runProductId?: string | null) => {
      if (runProductId) {
        setProductId(runProductId);
      }
      router.push("/experiments");
    },
    [router, setProductId],
  );

  const handleSaveTone = useCallback(async () => {
    if (!simulationRun) return;
    await updateSimulationTone(simulationRun.run_id, simulationTone, userId);
  }, [simulationRun, simulationTone, userId]);

  const handleClearTone = useCallback(async () => {
    setSimulationTone("");
    if (!simulationRun) return;
    await updateSimulationTone(simulationRun.run_id, "", userId);
  }, [simulationRun, userId]);

  const handleSaveProductCopy = useCallback(async () => {
    if (!selectedSimulationProductId) return;
    const response = await updateProductCopy(
      {
        product_id: selectedSimulationProductId,
        description: productCopy.trim(),
      },
      userId,
    );
    const updated = response.product;
    if (updated) {
      setSimulationProducts((current) =>
        current.map((item) =>
          item.id === updated.id
            ? {
                ...item,
                description: updated.description ?? item.description,
                metadata: updated.metadata ?? item.metadata,
              }
            : item,
        ),
      );
    }
    setProductCopySaved("Product copy saved.");
    window.setTimeout(() => setProductCopySaved(null), 2500);
  }, [productCopy, selectedSimulationProductId, userId]);

  const handleToneFromBrand = useCallback(async () => {
    try {
      const response = await requestBrandTone(simulationRun?.run_id, userId);
      setSimulationToneNotice(response.message);
      if (response.tone) {
        setSimulationToneSuggestion(response.tone);
        if (!simulationTone) {
          setSimulationTone(response.tone);
        }
      }
      window.setTimeout(() => setSimulationToneNotice(null), 2600);
    } catch {
      setSimulationToneNotice("Brand tone import is not ready yet.");
    }
  }, [simulationRun, simulationTone, userId]);

  const handleAttachRun = useCallback(
    async (runId: string) => {
      if (!productId) return;
      const response = await attachSimulationProduct(
        runId,
        productId,
        brandId ?? undefined,
        userId,
      );
      setSimulationRuns((current) =>
        current.map((run) =>
          run.id === runId
            ? {
                ...run,
                product_id: response.product_id ?? productId,
                brand_id: response.brand_id ?? brandId ?? null,
              }
            : run,
        ),
      );
    },
    [brandId, productId, userId],
  );

  const handleCloseHistory = useCallback(() => {
    if (isHistoryClosing) return;
    setHistoryClosing(true);
    window.setTimeout(() => {
      setHistoryOpen(false);
      setHistoryClosing(false);
    }, 200);
  }, [isHistoryClosing]);

  const confirmDeleteSession = useCallback(async () => {
    if (!deleteTargetId) return;
    try {
      await deleteConversationSession(deleteTargetId, userId);
      setSessions((current) => current.filter((item) => item.id !== deleteTargetId));
    } finally {
      setDeleteTargetId(null);
    }
  }, [deleteTargetId, userId]);

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
        activeSessionId={null}
        onClose={handleCloseHistory}
        onSelect={(selectedId) => {
          router.push(`/?session=${selectedId}`);
          handleCloseHistory();
        }}
        onRequestDelete={(sessionId) => setDeleteTargetId(sessionId)}
      />
      <main className="main main--detail">
        <div className="detail">
          <DetailHeader
            title="Simulation Sandbox"
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/")}
          />
          <SimulationPanel
            query={simulationScenario}
            scenarioValue={simulationScenario}
            onScenarioChange={(value) => {
              setSimulationScenario(value);
              setSimulationScenarioDirty(true);
            }}
            productCopy={productCopy}
            onProductCopyChange={setProductCopy}
            onProductCopySave={handleSaveProductCopy}
            productCopySaved={productCopySaved}
            brandToneSummary={brandToneSummary}
            toneSuggestion={simulationToneSuggestion}
            toneValue={simulationTone}
            toneNotice={simulationToneNotice}
            onToneChange={setSimulationTone}
            onToneUseSuggestion={() =>
              setSimulationTone(simulationToneSuggestion ?? "")
            }
            onToneSave={handleSaveTone}
            onToneClear={handleClearTone}
            onToneFromBrand={handleToneFromBrand}
            run={simulationRun}
            optimized={simulationOptimized}
            retest={simulationRetest}
            products={simulationProducts}
            selectedProductId={selectedSimulationProductId}
            loading={simulationLoading}
            canRun={Boolean(simulationScenario.trim() && simulationProducts.length > 0)}
            canOptimize={Boolean(simulationRun?.result?.gap_analysis?.length)}
            canRetest={Boolean(simulationRun && simulationOptimized)}
            onRun={handleRunSimulation}
            onOptimize={handleOptimizeSimulation}
            onRetest={handleRetestSimulation}
            onSelectProduct={setSelectedSimulationProductId}
          />
          <SimulationLessons lessons={simulationLessons} />
          <SimulationHistory
            runs={simulationRuns}
            activeRunId={simulationRun?.run_id}
            onSelect={handleSelectSimulationRun}
            onAttach={handleAttachRun}
            attachLabel={productName}
            attachDisabled={!productId}
            onOpenExperiments={handleOpenExperiments}
          />
          {simulationScenarioDirty && (
            <div className="detail__note">
              Scenario edited locally. Run to refresh results.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
