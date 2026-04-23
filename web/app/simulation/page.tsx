"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
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
  Experiment,
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
  getBrand,
  attachSimulationProduct,
  listConversationSessions,
  deleteConversationSession,
  deleteExperiment,
  deleteSimulationRun,
  listExperiments,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { SimulationPanel } from "../../components/simulation/SimulationPanel";
import { SimulationHistory } from "../../components/simulation/SimulationHistory";
import { SimulationLessons } from "../../components/simulation/SimulationLessons";
import { useTenant } from "../../components/tenant/TenantProvider";
import { buildExperimentHref, buildSimulationHref, buildValidationHref } from "../../lib/routes";
import { buildTenantStorageKey } from "../../lib/storage";

function filterProductsForBrand(
  products: SimulationProduct[],
  activeBrandId: string | null,
): SimulationProduct[] {
  if (!activeBrandId) return products;
  return products.filter((product) => {
    if (typeof product.brand_id === "string" && product.brand_id === activeBrandId) {
      return true;
    }
    return product.source === "catalog";
  });
}

export default function SimulationPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const { clientId, productId, productName, brandId, setProductId, setClientId } =
    useTenant();
  const storageClientId =
    clientId ??
    (typeof window !== "undefined"
      ? window.localStorage.getItem("client_id")
      : null) ??
    undefined;
  const storageKey = useMemo(
    () => buildTenantStorageKey("intentionality.simulation", userId, storageClientId),
    [storageClientId, userId],
  );
  const simulationLatestStorageKey = useMemo(
    () => buildTenantStorageKey("intentionality.simulation.latest", userId, storageClientId),
    [storageClientId, userId],
  );
  const runIdParam = searchParams.get("run_id")?.trim() || "";
  const experimentIdParam = searchParams.get("experiment_id")?.trim() || "";
  const evidenceStorageKey = useMemo(() => {
    const clientTag = storageClientId ? `.${storageClientId}` : "";
    return userId
      ? `intentionality.evidence.${userId}${clientTag}`
      : `intentionality.evidence.anonymous${clientTag}`;
  }, [storageClientId, userId]);
  const lastSessionKey = useMemo(() => {
    const clientTag = storageClientId ? `.${storageClientId}` : "";
    return userId
      ? `intentionality.last_session.${userId}${clientTag}`
      : `intentionality.last_session.anonymous${clientTag}`;
  }, [storageClientId, userId]);
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
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedSimulationProductId, setSelectedSimulationProductId] =
    useState<string | null>(null);
  const [simulationToneSuggestion, setSimulationToneSuggestion] = useState<string | null>(null);
  const [simulationTone, setSimulationTone] = useState("");
  const [simulationToneNotice, setSimulationToneNotice] = useState<string | null>(null);
  const [productCopy, setProductCopy] = useState("");
  const [feedPreview, setFeedPreview] = useState<{ acp?: string; ucp?: string } | null>(
    null,
  );
  const [brandToneSummary, setBrandToneSummary] = useState<string | null>(null);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [hasHydrated, setHasHydrated] = useState(false);
  const [evidenceSummary, setEvidenceSummary] = useState<{
    intentSignal: string | null;
    total: number;
    rank: number | null;
    alignment: number | null;
    discovered: boolean;
    focusHint: string | null;
  } | null>(null);
  const [optimizationMode, setOptimizationMode] = useState<"copy" | "feed" | "both">(
    "both",
  );
  const [simulationSourceSession, setSimulationSourceSession] = useState<string | null>(null);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [simulationSecondaryOpen, setSimulationSecondaryOpen] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const legacyUserKey = userId
      ? `intentionality.simulation.${userId}`
      : "intentionality.simulation.anonymous";
    const keys = [
      storageKey,
      simulationLatestStorageKey,
      legacyUserKey,
      "intentionality.simulation.latest",
      "intentionality.simulation.anonymous",
    ];
    const raw = keys.map((key) => localStorage.getItem(key)).find(Boolean);
    if (!raw) {
      setHasHydrated(true);
      return;
    }
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
    } finally {
      setHasHydrated(true);
    }
  }, [simulationLatestStorageKey, storageKey, userId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const rawEvidence = localStorage.getItem(evidenceStorageKey);
    if (!rawEvidence) {
      setEvidenceSummary(null);
      return;
    }
    try {
      const parsed = JSON.parse(rawEvidence) as {
        analysis?: {
          intent?: Record<string, unknown> | null;
          goals?: string[];
          evidence_products?: { id?: string }[];
          alignment_scores?: { product_id?: string; score?: number }[];
        };
      };
      const analysis = parsed.analysis;
      if (!analysis) {
        setEvidenceSummary(null);
        return;
      }
      const intentSignal =
        (analysis.intent?.primary_goal as string | undefined) ??
        (analysis.intent?.label as string | undefined) ??
        analysis.goals?.[0] ??
        null;
      const total = analysis.evidence_products?.length ?? 0;
      const scores = (analysis.alignment_scores ?? []).filter(
        (item) => item.product_id,
      );
      const sorted = [...scores].sort(
        (a, b) => (b.score ?? 0) - (a.score ?? 0),
      );
      const targetId = selectedSimulationProductId ?? productId ?? null;
      const idx = targetId
        ? sorted.findIndex((item) => item.product_id === targetId)
        : -1;
      const discovered = idx >= 0;
      const rank = discovered ? idx + 1 : null;
      const alignment = discovered ? sorted[idx].score ?? null : null;
      const focusHint = !discovered
        ? "depth"
        : rank && rank > 3
        ? "depth"
        : "breadth";
      setEvidenceSummary({
        intentSignal,
        total,
        rank,
        alignment,
        discovered,
        focusHint,
      });
    } catch {
      setEvidenceSummary(null);
    }
  }, [
    evidenceStorageKey,
    productId,
    selectedSimulationProductId,
    simulationScenario,
  ]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!hasHydrated) return;
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
    localStorage.setItem(simulationLatestStorageKey, JSON.stringify(payload));
  }, [
    hasHydrated,
    simulationOptimized,
    simulationProducts,
    simulationRetest,
    simulationRun,
    simulationScenario,
    simulationTone,
    simulationToneSuggestion,
    selectedSimulationProductId,
    storageKey,
    simulationLatestStorageKey,
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
    if (userId) {
      void listExperiments(userId).then((response) => {
        setExperiments(response.experiments ?? []);
      });
    }
  }, [userId, clientId]);

  useEffect(() => {
    if (!brandId) return;
    let cancelled = false;
    void listProductsByBrand(brandId, userId).then((response) => {
      if (cancelled) return;
      const items = response.products ?? [];
      if (items.length === 0) return;
      const toText = (value: unknown, fallback = "") =>
        typeof value === "string" && value.trim() ? value : fallback;
      const mapped = items.map((product) => ({
        id: product.id,
        name: product.name,
        description: toText(
          product.description ??
            toText((product.metadata as Record<string, unknown> | undefined)?.description),
          product.name,
        ),
        source: "catalog",
        brand_id: product.brand_id ?? brandId ?? undefined,
        url:
          (product.metadata as Record<string, unknown> | undefined)?.product_url as
            | string
            | undefined,
        price:
          typeof product.metadata?.price === "number"
            ? product.metadata?.price
            : undefined,
        confidence: 0.6,
        metadata: {
          ...(product.metadata ?? {}),
          feed_description:
            toText((product.metadata as Record<string, unknown>)?.feed_description) ||
            toText(product.description) ||
            toText((product.metadata as Record<string, unknown>)?.description) ||
            product.name,
          acp: {
            item_id: product.id,
            title: product.name,
            description:
              toText(
                (
                  ((product.metadata as Record<string, unknown>)?.acp as
                    | Record<string, unknown>
                    | undefined)
                )?.description,
              ) ||
              toText((product.metadata as Record<string, unknown>)?.feed_description) ||
              toText(product.description) ||
              toText((product.metadata as Record<string, unknown>)?.description) ||
              product.name,
            url:
              (product.metadata?.product_url as string | undefined) ??
              (product.metadata?.site_url as string | undefined) ??
              undefined,
            image_url:
              (product.metadata?.image_url as string | undefined) ??
              (product.metadata?.image as string | undefined) ??
              undefined,
            price:
              typeof product.metadata?.price === "number"
                ? product.metadata?.price
                : undefined,
            availability:
              (product.metadata?.availability as string | undefined) ?? "in_stock",
            brand:
              (product.metadata?.brand as string | undefined) ?? product.name,
            seller_name:
              (product.metadata?.merchant_name as string | undefined) ??
              product.name,
            seller_url:
              (product.metadata?.site_url as string | undefined) ??
              (product.metadata?.product_url as string | undefined) ??
              undefined,
            is_eligible_search: true,
            is_eligible_checkout: true,
            updated_at: new Date().toISOString(),
          },
          ucp: {
            offer_url:
              (product.metadata?.product_url as string | undefined) ??
              (product.metadata?.site_url as string | undefined) ??
              undefined,
            merchant_name:
              (product.metadata?.merchant_name as string | undefined) ??
              product.name,
            description:
              toText(
                (
                  ((product.metadata as Record<string, unknown>)?.ucp as
                    | Record<string, unknown>
                    | undefined)
                )?.description,
              ) ||
              toText((product.metadata as Record<string, unknown>)?.feed_description) ||
              toText(product.description) ||
              toText((product.metadata as Record<string, unknown>)?.description) ||
              product.name,
            price:
              typeof product.metadata?.price === "number"
                ? product.metadata?.price
                : undefined,
            currency: "USD",
            availability:
              (product.metadata?.availability as string | undefined) ?? "in_stock",
            available_for_sale: true,
          },
        },
      }));
      setSimulationProducts((current) => {
        const currentById = new Map(current.map((item) => [item.id, item]));
        return mapped.map((item) => {
          const existing = currentById.get(item.id);
          if (!existing) return item;
          return {
            ...item,
            description: existing.description || item.description,
            confidence: existing.confidence ?? item.confidence,
            metadata: {
              ...item.metadata,
              ...(existing.metadata ?? {}),
            },
          };
        });
      });
      const initial =
        productId && mapped.some((p) => p.id === productId)
          ? productId
          : mapped[0].id;
      setSelectedSimulationProductId((prev) => prev ?? initial);
      if (!productId) {
        setProductId(initial);
      }
      const selected =
        mapped.find((item) => item.id === (productId ?? initial)) ?? mapped[0];
      const creative = (selected?.metadata as Record<string, unknown> | undefined)?.creative as
        | Record<string, unknown>
        | undefined;
      setProductCopy(
        (creative?.manual_copy as string | undefined) ??
          selected?.description ??
          "",
      );
    });
    return () => {
      cancelled = true;
    };
  }, [brandId, productId, setProductId, userId]);

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
    const metadata = (selected.metadata as Record<string, unknown> | undefined) ?? {};
    const acpMeta = (metadata.acp as Record<string, unknown> | undefined) ?? {};
    const ucpMeta = (metadata.ucp as Record<string, unknown> | undefined) ?? {};
    setProductCopy(
      (creative?.manual_copy as string | undefined) ??
        selected.description ??
        "",
    );
    const acp = {
      item_id: selected.id,
      title: selected.name,
      description:
        (acpMeta.description as string | undefined) ??
        (metadata.feed_description as string | undefined) ??
        selected.description ??
        "",
      price: selected.price ? `${selected.price} USD` : undefined,
      url:
        (acpMeta.url as string | undefined) ??
        (metadata.product_url as string | undefined) ??
        selected.url,
      availability: "in_stock",
      is_eligible_search: true,
      is_eligible_checkout: true,
    };
    const ucp = {
      product_id: selected.id,
      name: selected.name,
      description:
        (ucpMeta.description as string | undefined) ??
        (metadata.feed_description as string | undefined) ??
        selected.description ??
        "",
      price: selected.price ?? null,
      currency: "USD",
      available_for_sale: true,
      product_url:
        (ucpMeta.product_url as string | undefined) ??
        (metadata.product_url as string | undefined) ??
        selected.url ??
        null,
    };
    setFeedPreview({
      acp: JSON.stringify(acp, null, 2),
      ucp: JSON.stringify(ucp, null, 2),
    });
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
      const scopedProducts = filterProductsForBrand(response.run.products ?? [], brandId);
      if (scopedProducts.length > 0) {
        setSimulationProducts(scopedProducts);
      } else if (!brandId) {
        setSimulationProducts(response.run.products ?? []);
      }
      if (
        response.run.product_id &&
        (!brandId || scopedProducts.some((item) => item.id === response.run.product_id))
      ) {
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
  }, [brandId, searchParams, setProductId, simulationRun?.run_id, simulationTone, userId]);

  useEffect(() => {
    const runIdParam = searchParams.get("run_id");
    if (runIdParam) return;
    const sessionParam = searchParams.get("session");
    if (!sessionParam) return;
    let cancelled = false;
    const hydrateFromSession = async () => {
      let resolvedClientId: string | null = storageClientId ?? clientId ?? null;
      if (!resolvedClientId && userId) {
        try {
          const response = await listConversationSessions(userId);
          const match = response.sessions.find((session) => session.id === sessionParam);
          resolvedClientId =
            typeof match?.client_id === "string" ? match.client_id : null;
        } catch {
          // ignore and fall back to current client scope
        }
      }
      if (resolvedClientId && resolvedClientId !== clientId) {
        setClientId(resolvedClientId);
      }
      const response = await getConversationSnapshot(
        sessionParam,
        userId,
        resolvedClientId ?? clientId ?? storageClientId ?? undefined,
      );
      if (cancelled) return;
      const state =
        (response.snapshot?.session?.state as Record<string, unknown> | undefined) ?? undefined;
      const scenario =
        (state?.last_query as string | undefined) ??
        response.plan?.query ??
        "";
      const stateProducts = (state?.last_products as SimulationProduct[]) ?? [];
      const research = response.plan?.research_results ?? response.plan?.products ?? [];
      const researchProducts = research.map((item) => ({
        id: item.id ?? item.name ?? "",
        name: item.name ?? "Result",
        description: item.description ?? item.name ?? "",
        source: item.source ?? "research",
        url: item.offer_url ?? undefined,
        price: item.price ?? undefined,
        confidence: item.confidence ?? undefined,
        metadata: {
          alignment_score: item.alignment_score,
          alignment_reasoning: item.alignment_reasoning,
        },
      })) as SimulationProduct[];
      const products = stateProducts.length > 0 ? stateProducts : researchProducts;
      const scopedProducts = filterProductsForBrand(products, brandId);
      if (scenario) {
        setSimulationScenario(scenario);
        setSimulationScenarioDirty(false);
      }
      if (!brandId && scopedProducts.length > 0) {
        setSimulationProducts(scopedProducts);
      }
      if (scopedProducts.length > 0) {
        const selected =
          (state?.last_product_id as string | undefined) ?? scopedProducts[0]?.id ?? null;
        if (!brandId || scopedProducts.some((item) => item.id === selected)) {
          setSelectedSimulationProductId(selected);
          if (selected) {
            setProductId(selected);
          }
        }
      }
      setSimulationSourceSession(sessionParam);
    };
    void hydrateFromSession();
    return () => {
      cancelled = true;
    };
  }, [brandId, clientId, searchParams, setClientId, setProductId, storageClientId, userId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!userId || simulationScenario) return;
    const runIdParam = searchParams.get("run_id");
    if (runIdParam) return;
    const sessionParam = searchParams.get("session");
    if (sessionParam) return;
    const lastSessionId = window.localStorage.getItem(lastSessionKey);
    if (!lastSessionId) return;
    let cancelled = false;
    void getConversationSnapshot(
      lastSessionId,
      userId,
      storageClientId ?? clientId ?? undefined,
    ).then((snapshot) => {
      if (cancelled) return;
      const scenario = snapshot.plan?.query ?? "";
      const research =
        snapshot.plan?.research_results ?? snapshot.plan?.products ?? [];
      if (scenario) {
        setSimulationScenario(scenario);
        setSimulationScenarioDirty(false);
      }
      if (research.length > 0) {
        const products = research.map((item) => ({
          id: item.id ?? item.name ?? "",
          name: item.name ?? "Result",
          description: item.description ?? item.name ?? "",
          source: item.source ?? "research",
          url: item.offer_url ?? undefined,
          price: item.price ?? undefined,
          confidence: item.confidence ?? undefined,
          metadata: {
            alignment_score: item.alignment_score,
            alignment_reasoning: item.alignment_reasoning,
          },
        })) as SimulationProduct[];
        const scopedProducts = filterProductsForBrand(products, brandId);
        if (!brandId && scopedProducts.length > 0) {
          setSimulationProducts(scopedProducts);
          const selected = scopedProducts[0]?.id ?? null;
          setSelectedSimulationProductId(selected);
        }
      }
      setSimulationSourceSession(lastSessionId);
    });
    return () => {
      cancelled = true;
    };
  }, [
    brandId,
    clientId,
    lastSessionKey,
    searchParams,
    simulationScenario,
    storageClientId,
    userId,
  ]);

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
      const winnerId = response.result?.winner_id;
      if (winnerId && simulationProducts.some((item) => item.id === winnerId)) {
        setSelectedSimulationProductId(winnerId);
      }
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
      if (optimizationMode === "feed") {
        return;
      }
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
    [optimizationMode, simulationRun, simulationTone, userId],
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
      const scopedProducts = filterProductsForBrand(run.products ?? [], brandId);
      if (scopedProducts.length > 0) {
        setSimulationProducts(scopedProducts);
      } else if (!brandId) {
        setSimulationProducts(run.products ?? []);
      }
      setSimulationScenario(run.query ?? "");
      setSimulationScenarioDirty(false);
      const scenario = (run.scenario as Record<string, unknown> | undefined) || {};
      const confirmedTone = (scenario.confirmed_tone as string | undefined) ?? "";
      const suggestedTone = (scenario.tone_suggestion as string | undefined) ?? null;
      setSimulationToneSuggestion(run.result?.tone?.summary ?? suggestedTone ?? null);
      setSimulationTone(confirmedTone || run.result?.tone?.summary || "");
      if (scopedProducts.length) {
        setSelectedSimulationProductId(scopedProducts[0].id);
      }
    },
    [brandId, userId],
  );

  const handleOpenExperiments = useCallback(
    (activeRunId: string, runProductId?: string | null) => {
      if (runProductId) {
        setProductId(runProductId);
      }
      router.push(buildExperimentHref(experimentIdParam || null, { runId: activeRunId }));
    },
    [experimentIdParam, router, setProductId],
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

  const handleProductCopyChange = useCallback(
    (value: string) => {
      setProductCopy(value);
      if (!selectedSimulationProductId) return;
      setSimulationProducts((current) =>
        current.map((item) =>
          item.id === selectedSimulationProductId
            ? {
                ...item,
                description: value,
              }
            : item,
        ),
      );
    },
    [selectedSimulationProductId],
  );

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

  const simulationBestScore = useMemo(() => {
    const scores = simulationRun?.result?.scores ?? [];
    if (!scores.length) return null;
    return [...scores].sort((a, b) => b.score - a.score)[0] ?? null;
  }, [simulationRun?.result?.scores]);

  const simulationSelectedScore = useMemo(() => {
    if (!selectedSimulationProductId) return null;
    return (
      simulationRun?.result?.scores?.find(
        (score) => score.product_id === selectedSimulationProductId,
      ) ?? null
    );
  }, [selectedSimulationProductId, simulationRun?.result?.scores]);

  const simulationSelectedProductLabel = useMemo(() => {
    if (!selectedSimulationProductId) return "No product selected";
    return (
      simulationProducts.find((product) => product.id === selectedSimulationProductId)?.name ??
      selectedSimulationProductId
    );
  }, [selectedSimulationProductId, simulationProducts]);

  const simulationLift = useMemo(() => {
    const targetId = simulationOptimized?.optimized.id;
    if (!targetId) return null;
    const beforeScore =
      simulationRun?.result?.scores?.find((score) => score.product_id === targetId)?.score ??
      null;
    const afterScore =
      simulationRetest?.result?.scores?.find((score) => score.product_id === targetId)?.score ??
      null;
    if (beforeScore === null || afterScore === null) return null;
    return (afterScore - beforeScore) * 100;
  }, [simulationOptimized?.optimized.id, simulationRetest?.result?.scores, simulationRun?.result?.scores]);

  const simulationFlowSteps = useMemo(() => {
    const scenarioReady = Boolean(simulationScenario.trim() && simulationProducts.length > 0);
    const runReady = Boolean(simulationRun);
    const targetReady = Boolean(selectedSimulationProductId);
    const optimizedReady = Boolean(simulationOptimized);
    const retestReady = Boolean(simulationRetest);
    const decisionReady = Boolean(simulationRetest || simulationOptimized);
    return [
      { id: 1, label: "Define scenario", done: scenarioReady },
      { id: 2, label: "Run simulation", done: runReady },
      { id: 3, label: "Select target product", done: targetReady },
      { id: 4, label: "Generate optimization", done: optimizedReady },
      { id: 5, label: "Retest outcome", done: retestReady },
      { id: 6, label: "Decide next move", done: decisionReady },
    ];
  }, [
    selectedSimulationProductId,
    simulationOptimized,
    simulationProducts.length,
    simulationRetest,
    simulationRun,
    simulationScenario,
  ]);

  const simulationCurrentStep = useMemo(
    () => simulationFlowSteps.find((step) => !step.done)?.id ?? 6,
    [simulationFlowSteps],
  );

  const simulationNextAction = useMemo(() => {
    if (!simulationScenario.trim() || simulationProducts.length === 0) {
      return {
        label: "Define scenario and products",
        helper: "Set buyer intent and ensure at least one product is loaded.",
        action: "define" as const,
      };
    }
    if (!simulationRun) {
      return {
        label: "Run simulation now",
        helper: "Generate baseline intent-alignment scores before optimization.",
        action: "run" as const,
      };
    }
    if (!selectedSimulationProductId) {
      return {
        label: "Select target product",
        helper: "Pick the product you want to optimize and retest.",
        action: "select_target" as const,
      };
    }
    if (!simulationOptimized && optimizationMode !== "feed") {
      return {
        label: "Generate optimization",
        helper: "Create a revised copy/feed candidate for the selected product.",
        action: "optimize" as const,
      };
    }
    if (
      !simulationRetest &&
      simulationOptimized &&
      optimizationMode !== "feed"
    ) {
      return {
        label: "Retest optimized variant",
        helper: "Measure lift against the baseline run before deciding next steps.",
        action: "retest" as const,
      };
    }
    return {
      label: "Open Experiments for controlled validation",
      helper: "Move the best candidate into Experiment flow for decision-grade testing.",
      action: "open_experiments" as const,
    };
  }, [
    optimizationMode,
    selectedSimulationProductId,
    simulationOptimized,
    simulationProducts.length,
    simulationRetest,
    simulationRun,
    simulationScenario,
  ]);

  const handleRunSimulationNextAction = useCallback(() => {
    switch (simulationNextAction.action) {
      case "define":
        return;
      case "run":
        void handleRunSimulation();
        return;
      case "select_target":
        if (simulationBestScore?.product_id) {
          setSelectedSimulationProductId(simulationBestScore.product_id);
        }
        return;
      case "optimize":
        void handleOptimizeSimulation(selectedSimulationProductId ?? undefined);
        return;
      case "retest":
        void handleRetestSimulation();
        return;
      case "open_experiments":
        handleOpenExperiments(simulationRun?.run_id ?? runIdParam, selectedSimulationProductId);
        return;
      default:
        return;
    }
  }, [
    handleOpenExperiments,
    handleOptimizeSimulation,
    handleRetestSimulation,
    handleRunSimulation,
    runIdParam,
    selectedSimulationProductId,
    simulationBestScore?.product_id,
    simulationNextAction.action,
    simulationRun?.run_id,
  ]);

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
          router.push(
            buildSimulationHref(run.id, { experimentId: experimentIdParam || null }),
          );
          handleCloseHistory();
        }}
        onSelectExperiment={(experiment) => {
          router.push(buildExperimentHref(experiment.id, { runId: runIdParam || null }));
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
            title="Simulation Sandbox"
            onMenu={() => setSidebarOpen(true)}
            onBack={() => {
              if (runIdParam) {
                router.push(
                  buildValidationHref({
                    experimentId: experimentIdParam || null,
                    runId: runIdParam,
                  }),
                );
                return;
              }
              router.push("/lab");
            }}
            backLabel={runIdParam ? "Back to validation" : undefined}
          />
          {runIdParam ? (
            <section className="panel__notice panel__notice--info">
              <strong>Run context preserved:</strong> this simulation view was opened from run{" "}
              <span className="panel__badge panel__badge--secondary">{runIdParam.slice(0, 8)}</span>.
              <div className="panel__actions">
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() => {
                    router.push(
                      buildValidationHref({
                        experimentId: experimentIdParam || null,
                        runId: runIdParam,
                      }),
                    );
                  }}
                >
                  Return to validation
                </button>
                <button
                  type="button"
                  className="panel__action panel__action--ghost"
                  onClick={() =>
                    handleOpenExperiments(runIdParam, selectedSimulationProductId ?? productId)
                  }
                >
                  Open experiments
                </button>
              </div>
            </section>
          ) : null}
          <section className="panel__notice panel__notice--info">
            <strong>Lab signal:</strong> Simulation scores are directional and
            should be validated with live outcomes before rollout.
          </section>
          <section className="panel__card panel__card--primary simulation-flow">
            <div className="panel__header">
              <h3>Simulation Flow</h3>
              <span className="panel__muted">Current step: {simulationCurrentStep} / 6</span>
            </div>
            <div className="flow-rail__steps">
              {simulationFlowSteps.map((step) => (
                <div
                  key={step.id}
                  className={`flow-rail__step ${
                    step.done ? "is-done" : step.id === simulationCurrentStep ? "is-current" : ""
                  }`}
                >
                  <span className="flow-rail__index">{step.id}</span>
                  <span className="flow-rail__label">{step.label}</span>
                  <span className="flow-rail__status">
                    {step.done ? "Done" : step.id === simulationCurrentStep ? "Current" : "Pending"}
                  </span>
                </div>
              ))}
            </div>
            <div className="panel__separator" />
            <section className="panel__notice panel__notice--info flow-next-action">
              <strong>Next recommended action:</strong> {simulationNextAction.label}
              <p className="panel__muted">{simulationNextAction.helper}</p>
              <div className="panel__actions panel__actions--priority">
                <button
                  type="button"
                  className="panel__action panel__action--prominent"
                  onClick={handleRunSimulationNextAction}
                >
                  {simulationNextAction.label}
                </button>
              </div>
            </section>
            <div className="panel__separator" />
            <section className="panel__notice panel__notice--info outcome-snapshot">
              <div className="panel__meta">
                <strong>Outcome snapshot</strong>
                <span className="panel__badge panel__badge--secondary">Unified view</span>
              </div>
              <div className="outcome-snapshot__grid">
                <div className="outcome-snapshot__item">
                  <span className="outcome-snapshot__label">Winner</span>
                  <span className="outcome-snapshot__value">
                    {simulationBestScore?.product_id ?? "No run yet"}
                  </span>
                  <span className="panel__muted">
                    Score:{" "}
                    {typeof simulationBestScore?.score === "number"
                      ? `${Math.round(simulationBestScore.score * 100)}%`
                      : "—"}
                  </span>
                </div>
                <div className="outcome-snapshot__item">
                  <span className="outcome-snapshot__label">Selected target</span>
                  <span className="outcome-snapshot__value">
                    {simulationSelectedProductLabel}
                  </span>
                  <span className="panel__muted">
                    Alignment:{" "}
                    {typeof simulationSelectedScore?.score === "number"
                      ? `${Math.round(simulationSelectedScore.score * 100)}%`
                      : "—"}
                  </span>
                </div>
                <div className="outcome-snapshot__item">
                  <span className="outcome-snapshot__label">Retest / lift</span>
                  <span className="outcome-snapshot__value">
                    {simulationRetest ? "Retested" : simulationOptimized ? "Optimized only" : "Pending"}
                  </span>
                  <span className="panel__muted">
                    Lift:{" "}
                    {typeof simulationLift === "number"
                      ? `${simulationLift >= 0 ? "+" : ""}${simulationLift.toFixed(1)} pts`
                      : "—"}
                  </span>
                </div>
              </div>
            </section>
          </section>
          <SimulationPanel
            query={simulationScenario}
            scenarioValue={simulationScenario}
            onScenarioChange={(value) => {
              setSimulationScenario(value);
              setSimulationScenarioDirty(true);
            }}
            evidenceSummary={evidenceSummary}
            optimizationMode={optimizationMode}
            onOptimizationModeChange={setOptimizationMode}
            sourceSessionId={simulationSourceSession}
            productCopy={productCopy}
            onProductCopyChange={handleProductCopyChange}
            feedPreview={feedPreview}
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
            canOptimize={Boolean(
              simulationRun?.result?.gap_analysis?.length &&
                optimizationMode !== "feed",
            )}
            canRetest={Boolean(
              simulationRun && simulationOptimized && optimizationMode !== "feed",
            )}
            onRun={handleRunSimulation}
            onOptimize={handleOptimizeSimulation}
            onRetest={handleRetestSimulation}
            onSelectProduct={setSelectedSimulationProductId}
          />
          <section className="panel__card panel__card--secondary">
            <div className="panel__header">
              <h3>Secondary Records</h3>
              <button
                type="button"
                className="panel__action panel__action--ghost"
                onClick={() => setSimulationSecondaryOpen((open) => !open)}
              >
                {simulationSecondaryOpen ? "Hide secondary" : "Show secondary"}
              </button>
            </div>
            <p className="panel__subheading">Reference history</p>
            <p className="panel__step-helper">
              Keep focus on the active simulation flow; expand when you need past runs or lessons.
            </p>
            {!simulationSecondaryOpen ? (
              <p className="panel__muted">
                Secondary records are collapsed to reduce noise during active optimization.
              </p>
            ) : (
              <div className="panel__form">
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
              </div>
            )}
          </section>
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
