"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  analyzeEvidence,
  createBattery,
  deleteConversationSession,
  deleteExperiment,
  deleteSimulationRun,
  getConversationSnapshot,
  listConversationSessions,
  refreshResearch,
  optimizeRepresentation,
  listSimulationRuns,
  listSimulationLessons,
  sendConversationMessage,
  sendConversationMessageStreamWithEvents,
  startConversation,
  startConversationStreamWithEvents,
  verifyRecommendation,
  listExperiments,
  getLlmConfig,
  activateAdminLlmProvider,
} from "../lib/api";
import type {
  ConversationResponse,
  EvidenceAnalyzeResponse,
  RepresentationOptimizeResponse,
  RecommendationVerifyResponse,
  SessionSummary,
  SimulationProduct,
  SimulationRunSummary,
  SimulationLesson,
  Experiment,
  LLMConfigSummaryResponse,
} from "../lib/types";
import { ChatWindow, type Message } from "../components/chat/ChatWindow";
import Link from "next/link";
import { Sidebar } from "../components/layout/Sidebar";
import { GoalClarificationPanel } from "../components/values/GoalClarificationPanel";
import { IntentionalityProfileCard } from "../components/products/IntentionalityProfileCard";
import { IntentDisplay } from "../components/intent/IntentDisplay";
import { ProductReasoning } from "../components/products/ProductReasoning";
import { HistoryDrawer } from "../components/layout/HistoryDrawer";
import { useUser } from "@clerk/nextjs";
import { useTenant } from "../components/tenant/TenantProvider";
import { buildExperimentHref, buildSimulationHref } from "../lib/routes";
import { buildTenantStorageKey } from "../lib/storage";

const CHAT_PROVIDER_MODELS: Record<string, string[]> = {
  openrouter: ["openai/gpt-oss-120b"],
  openai: ["gpt-5.2-2025-12-11"],
  anthropic: ["claude-sonnet-4-5-20250929"],
  gemini: ["gemini-3-flash-preview"],
};

const CHAT_PROVIDER_LABELS: Record<string, string> = {
  openrouter: "OpenRouter",
  openai: "OpenAI",
  anthropic: "Claude (Anthropic)",
  gemini: "Gemini",
};

type SessionResearchState = {
  items?: ConversationResponse["plan"] extends infer P
    ? P extends { research_results?: infer R }
      ? R
      : never
    : never;
  alignment?: {
    per_item?: {
      product_id?: string;
      score?: number;
      alignment_reasoning?: string;
    }[];
  };
};

type SessionState = {
  clarification_state?: ConversationResponse["goal_state"];
  last_intent?: ConversationResponse["intent"];
  last_research?: SessionResearchState;
  last_query?: string | null;
  last_products?: SimulationProduct[];
  last_product_id?: string | null;
  last_profiles?: EvidenceAnalyzeResponse["profiles"];
};

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinkingMessage, setThinkingMessage] = useState<string | null>(null);
  const [plan, setPlan] = useState<ConversationResponse["plan"]>();
  const [clarifications, setClarifications] = useState<string[]>([]);
  const [productReasoning, setProductReasoning] = useState<
    ConversationResponse["product_explanations"]
  >([]);
  const [researchResults, setResearchResults] = useState<
    NonNullable<ConversationResponse["plan"]>["research_results"]
  >([]);
  const [goalState, setGoalState] = useState<ConversationResponse["goal_state"]>();
  const [intent, setIntent] = useState<ConversationResponse["intent"]>();
  const [evidenceAnalysis, setEvidenceAnalysis] = useState<EvidenceAnalyzeResponse | null>(null);
  const [evidenceOptimization, setEvidenceOptimization] =
    useState<RepresentationOptimizeResponse | null>(null);
  const [evidenceVerification, setEvidenceVerification] =
    useState<RecommendationVerifyResponse | null>(null);
  const [simulationScenario, setSimulationScenario] = useState("");
  const [simulationScenarioDirty, setSimulationScenarioDirty] = useState(false);
  const [simulationTone, setSimulationTone] = useState("");
  const [simulationProducts, setSimulationProducts] = useState<SimulationProduct[]>([]);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [simulationLessons, setSimulationLessons] = useState<SimulationLesson[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [llmConfig, setLlmConfig] = useState<LLMConfigSummaryResponse | null>(null);
  const [llmConfigError, setLlmConfigError] = useState<string | null>(null);
  const [chatProvider, setChatProvider] = useState<string>("openrouter");
  const [chatModel, setChatModel] = useState<string>("");
  const [labOperator, setLabOperator] = useState<ConversationResponse["lab_operator"] | null>(
    null,
  );
  const [selectedSimulationProductId, setSelectedSimulationProductId] =
    useState<string | null>(null);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [backgroundStatus, setBackgroundStatus] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [batteryStatus, setBatteryStatus] = useState<string | null>(null);
  const [researchStatus, setResearchStatus] = useState<string | null>(null);
  const [researchRefreshing, setResearchRefreshing] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const { user } = useUser();
  const searchParams = useSearchParams();
  const router = useRouter();
  const userId = user?.id ?? null;
  const { brandId, productId, clientId, setClientId } = useTenant();
  const storageClientId =
    clientId ??
    (typeof window !== "undefined"
      ? window.localStorage.getItem("client_id")
      : null) ??
    undefined;
  const storageKey = useMemo(() => {
    const clientTag = storageClientId ? `.${storageClientId}` : "";
    return userId
      ? `intentionality.sessions.${userId}${clientTag}`
      : `intentionality.sessions.anonymous${clientTag}`;
  }, [storageClientId, userId]);
  const lastSessionKey = useMemo(() => {
    const clientTag = storageClientId ? `.${storageClientId}` : "";
    return userId
      ? `intentionality.last_session.${userId}${clientTag}`
      : `intentionality.last_session.anonymous${clientTag}`;
  }, [storageClientId, userId]);
  const simulationStorageKey = useMemo(
    () => buildTenantStorageKey("intentionality.simulation", userId, storageClientId),
    [storageClientId, userId],
  );
  const simulationLatestStorageKey = useMemo(
    () => buildTenantStorageKey("intentionality.simulation.latest", userId, storageClientId),
    [storageClientId, userId],
  );
  const evidenceStorageKey = useMemo(() => {
    const clientTag = storageClientId ? `.${storageClientId}` : "";
    return userId
      ? `intentionality.evidence.${userId}${clientTag}`
      : `intentionality.evidence.anonymous${clientTag}`;
  }, [storageClientId, userId]);
  const alignmentStorageKey = useMemo(
    () => buildTenantStorageKey("intentionality.alignment", userId, storageClientId),
    [storageClientId, userId],
  );
  const chatModelOptions = useMemo(() => {
    const base = CHAT_PROVIDER_MODELS[chatProvider] ?? [];
    if (chatModel && !base.includes(chatModel)) {
      return [chatModel, ...base];
    }
    return base;
  }, [chatModel, chatProvider]);

  const updateSessions = useCallback(
    (updater: (current: SessionSummary[]) => SessionSummary[]) => {
      setSessions((current) => {
        const next = updater(current);
        if (userId) {
          localStorage.setItem(storageKey, JSON.stringify(next));
        }
        return next;
      });
    },
    [storageKey, userId],
  );

  useEffect(() => {
    if (!userId) return;
    void getLlmConfig(userId)
      .then((response) => {
        setLlmConfig(response);
        setLlmConfigError(null);
        const activeProvider =
          response.active_provider === "claude"
            ? "anthropic"
            : response.active_provider;
        const nextProvider =
          activeProvider ||
          (response.providers?.openrouter?.configured ? "openrouter" : "openai");
        const normalizedProvider = CHAT_PROVIDER_MODELS[nextProvider]
          ? nextProvider
          : "openrouter";
        setChatProvider(normalizedProvider);
        const providerConfig = response.providers?.[normalizedProvider];
        setChatModel(
          providerConfig?.model ||
            CHAT_PROVIDER_MODELS[normalizedProvider]?.[0] ||
            "",
        );
      })
      .catch((err) => {
        setLlmConfig(null);
        setLlmConfigError(err instanceof Error ? err.message : "Unable to load");
      });
  }, [userId]);

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

  const applyChatModel = useCallback(
    async (nextProvider: string, nextModel: string) => {
      if (!userId) return;
      try {
        await activateAdminLlmProvider({
          user_id: userId,
          provider: nextProvider,
          model: nextModel || undefined,
        });
        const summary = await getLlmConfig(userId);
        setLlmConfig(summary);
        setLlmConfigError(null);
      } catch (error) {
        setLlmConfigError("Unable to activate provider.");
      }
    },
    [userId],
  );

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

  const handleRefreshResearch = useCallback(async () => {
    if (!sessionId || !userId) {
      setResearchStatus("Start a chat first to refresh research.");
      window.setTimeout(() => setResearchStatus(null), 4000);
      return;
    }
    setResearchRefreshing(true);
    try {
      const response = await refreshResearch(sessionId, userId, lastQuery ?? undefined);
      setResearchResults(response.research_results ?? []);
      if (response.query) {
        setLastQuery(response.query);
      }
      setResearchStatus("Research refreshed.");
      window.setTimeout(() => setResearchStatus(null), 4000);
    } catch (error) {
      setResearchStatus(
        error instanceof Error ? error.message : "Unable to refresh research.",
      );
      window.setTimeout(() => setResearchStatus(null), 4000);
    } finally {
      setResearchRefreshing(false);
    }
  }, [lastQuery, sessionId, userId]);

  const resetConversation = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setPlan(undefined);
    setClarifications([]);
    setProductReasoning([]);
    setGoalState(undefined);
    setIntent(undefined);
    setResearchResults([]);
    setEvidenceAnalysis(null);
    setEvidenceOptimization(null);
    setEvidenceVerification(null);
    setSimulationProducts([]);
    setSelectedSimulationProductId(null);
    setSimulationScenarioDirty(false);
    setSimulationTone("");
    localStorage.removeItem(lastSessionKey);
  }, [lastSessionKey]);

  const upsertSession = useCallback(
    (session: SessionSummary) => {
      updateSessions((current) => {
        const filtered = current.filter((item) => item.id !== session.id);
        return [session, ...filtered].slice(0, 20);
      });
    },
    [updateSessions],
  );

  const sendMessage = useCallback(
    async (text: string, opts?: { skipEcho?: boolean }) => {
      if (!text.trim() || isStreaming) return;
      const isLabCommand = /^\/lab\b/i.test(text);
      if (!opts?.skipEcho) {
        setMessages((prev) => [...prev, { role: "user", content: text }]);
      }
      setIsStreaming(true);
      setThinkingMessage("Synthesizing the intent graph");
      const controller = new AbortController();
      abortRef.current = controller;
      let agentIndex: number | null = null;
      let receivedDelta = false;
      const applyDelta = (delta: string) => {
        if (!delta) return;
        receivedDelta = true;
        setMessages((prev) => {
          const next = [...prev];
          if (agentIndex === null) {
            agentIndex = next.length;
            next.push({ role: "agent", content: delta });
            return next;
          }
          const current = next[agentIndex];
          if (!current) return next;
          next[agentIndex] = { ...current, content: `${current.content}${delta}` };
          return next;
        });
      };
      const metadata = {
        brand_id: brandId ?? undefined,
        product_id: productId ?? undefined,
        client_id: clientId ?? undefined,
      };
      let response: ConversationResponse | null = null;
      try {
        if (!sessionId) {
          try {
            response = await startConversationStreamWithEvents(
              text,
              userId,
              metadata,
              { onDelta: applyDelta },
              controller.signal,
            );
          } catch {
            response = await startConversation(text, userId, metadata);
          }
          if (response) {
            setSessionId(response.session_id);
            upsertSession({
              id: response.session_id,
              preview: text,
              created_at: response.snapshot?.session?.created_at,
              last_turn_at: new Date().toISOString(),
            });
          }
        } else {
          try {
            response = await sendConversationMessageStreamWithEvents(
              sessionId,
              text,
              userId,
              metadata,
              { onDelta: applyDelta },
              controller.signal,
            );
          } catch {
            response = await sendConversationMessage(sessionId, text, userId, metadata);
          }
          if (response) {
            upsertSession({
              id: sessionId,
              preview: text,
              created_at: response.snapshot?.session?.created_at,
              last_turn_at: new Date().toISOString(),
            });
          }
        }
      } catch (error) {
        if ((error as Error).name === "AbortError") {
          return;
        }
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: `Error: ${(error as Error).message}` },
        ]);
      } finally {
        setIsStreaming(false);
        setThinkingMessage(null);
        abortRef.current = null;
      }

      if (!response) return;

      const clarification = response.clarification;
      if (clarification) {
        setMessages((prev) => [...prev, { role: "agent", content: clarification }]);
      }

      const operatorMessage = response.lab_operator?.message;
      if (typeof operatorMessage === "string" && operatorMessage) {
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: operatorMessage },
        ]);
        setLabOperator(response.lab_operator ?? null);
      }

      if (response.explanation && !receivedDelta) {
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: response.explanation! },
        ]);
      }
      setPlan(response.plan);
      setClarifications(response.plan?.clarifications ?? []);
      setProductReasoning(response.product_explanations ?? []);
      setGoalState(response.goal_state);
      setIntent(response.intent);
      setResearchResults(response.plan?.research_results ?? []);
      const nextQuery = response.plan?.query ?? text;
      setLastQuery(nextQuery);
      if (!simulationScenarioDirty) {
        setSimulationScenario(nextQuery);
      }

      if (isLabCommand) {
        return;
      }

      setBackgroundStatus("Analyzing evidence...");
      try {
        const analysis = await analyzeEvidence(text);
        setEvidenceAnalysis(analysis);
        setBackgroundStatus("Optimizing representation...");
        const optimization = await optimizeRepresentation(
          analysis.evidence_products,
          text,
          simulationTone || undefined,
        );
        setEvidenceOptimization(optimization);
        setBackgroundStatus("Verifying recommendations...");
        const verification = await verifyRecommendation(
          text,
          analysis.evidence_products,
          optimization.optimized,
        );
        setEvidenceVerification(verification);
        const products = (analysis.evidence_products ?? []).map((item) => ({
          id: item.id,
          name: item.name,
          description: item.description || item.raw_text || item.name,
          source: item.source,
          url: item.url,
          price: item.price,
          confidence: item.confidence,
          metadata: item.metadata,
        }));
        setSimulationProducts(products);
        if (products.length > 0) {
          setSelectedSimulationProductId(products[0].id);
        }
      } catch (error) {
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: `Error: ${(error as Error).message}` },
        ]);
      } finally {
        setBackgroundStatus(null);
      }
    },
    [
      brandId,
      clientId,
      isStreaming,
      productId,
      sessionId,
      simulationScenarioDirty,
      simulationTone,
      upsertSession,
      userId,
    ],
  );

  useEffect(() => {
    if (!isStreaming) return;
    const phrases = [
      "Synthesizing the intent graph",
      "Negotiating with the future you",
      "Asking the shoes nicely",
      "Calibrating the hypothesis engine",
      "Rehearsing the experiment",
      "Consulting the discovery oracle",
    ];
    let index = 0;
    const timer = window.setInterval(() => {
      index = (index + 1) % phrases.length;
      setThinkingMessage(phrases[index]);
    }, 2200);
    return () => window.clearInterval(timer);
  }, [isStreaming]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim() && !isStreaming) {
      void sendMessage(inputValue);
      setInputValue("");
    }
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim() && !isStreaming) {
        void sendMessage(inputValue);
        setInputValue("");
      }
    }
  };

  const hasInsights =
    clarifications.length > 0 ||
    goalState ||
    (plan?.products?.length ?? 0) > 0 ||
    intent?.primary_goal;

  useEffect(() => {
    const el = chatContainerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (!sessionId) return;
    localStorage.setItem(lastSessionKey, sessionId);
  }, [lastSessionKey, sessionId]);

  useEffect(() => {
    if (!isHistoryOpen) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        handleCloseHistory();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [handleCloseHistory, isHistoryOpen]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    const nextHeight = Math.min(el.scrollHeight, 220);
    el.style.height = `${nextHeight}px`;
  }, [inputValue]);

  useEffect(() => {
    if (!userId) return;
    const storedRaw = localStorage.getItem(storageKey);
    let storedSessions: SessionSummary[] = [];
    if (storedRaw) {
      try {
        storedSessions = JSON.parse(storedRaw) as SessionSummary[];
        setSessions(storedSessions);
      } catch {
        localStorage.removeItem(storageKey);
      }
    } else {
      setSessions([]);
    }
    void listConversationSessions(userId).then((response) => {
      const merged = new Map<string, SessionSummary>();
      response.sessions.forEach((session) => merged.set(session.id, session));
      storedSessions.forEach((session) => {
        if (!merged.has(session.id)) {
          merged.set(session.id, session);
        }
      });
      updateSessions(() => Array.from(merged.values()));
    });
  }, [storageKey, updateSessions, userId]);

  useEffect(() => {
    if (!userId) return;
    const loadSimulationData = async () => {
      try {
        const runs = await listSimulationRuns(userId);
        setSimulationRuns(runs.runs ?? []);
      } catch (error) {
        console.warn("Failed to load simulation runs", error);
      }
      try {
        const lessons = await listSimulationLessons(userId);
        setSimulationLessons(lessons.lessons ?? []);
      } catch (error) {
        console.warn("Failed to load simulation lessons", error);
      }
      try {
        const response = await listExperiments(userId);
        setExperiments(response.experiments ?? []);
      } catch (error) {
        console.warn("Failed to load experiments", error);
      }
    };
    void loadSimulationData();
  }, [userId, clientId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fallbackScenario = simulationScenario.trim() || lastQuery || "";
    const payload = {
      scenario: fallbackScenario,
      products: simulationProducts,
      selected_product_id: selectedSimulationProductId,
      tone: simulationTone,
    };
    localStorage.setItem(simulationStorageKey, JSON.stringify(payload));
    localStorage.setItem(simulationLatestStorageKey, JSON.stringify(payload));
  }, [
    simulationProducts,
    simulationScenario,
    simulationStorageKey,
    simulationLatestStorageKey,
    simulationTone,
    selectedSimulationProductId,
    lastQuery,
  ]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const payload = {
      analysis: evidenceAnalysis,
      optimization: evidenceOptimization,
      verification: evidenceVerification,
    };
    localStorage.setItem(evidenceStorageKey, JSON.stringify(payload));
  }, [evidenceAnalysis, evidenceOptimization, evidenceStorageKey, evidenceVerification]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const payload = {
      intent,
      goal_state: goalState,
      plan,
      clarifications,
      product_reasoning: productReasoning,
      research_results: researchResults,
      last_query: lastQuery,
    };
    localStorage.setItem(alignmentStorageKey, JSON.stringify(payload));
  }, [
    alignmentStorageKey,
    clarifications,
    goalState,
    intent,
    lastQuery,
    plan,
    productReasoning,
    researchResults,
  ]);


  const handleSelectSession = useCallback(
    async (selected: SessionSummary | string) => {
      const selectedId = typeof selected === "string" ? selected : selected.id;
      const selectedClientId =
        typeof selected === "string" ? null : selected.client_id ?? null;
      if (!selectedId) return;
      if (selectedClientId && selectedClientId !== clientId) {
        setClientId(selectedClientId);
      }
      const snapshot = await getConversationSnapshot(
        selectedId,
        userId,
        selectedClientId ?? clientId ?? undefined,
      );
      const turns = snapshot.snapshot?.turns ?? [];
      setSessionId(selectedId);
      setMessages(
        turns.map((turn) => ({
          role: turn.speaker,
          content: turn.content,
        })),
      );
      const state =
        (snapshot.snapshot?.session?.state as SessionState | undefined) ?? {};
      setGoalState(state.clarification_state as ConversationResponse["goal_state"]);
      setIntent(state.last_intent as ConversationResponse["intent"]);
      setResearchResults(state.last_research?.items ?? []);
      setLastQuery(state.last_query ?? null);
      setSimulationScenario(state.last_query ?? "");
      setSimulationScenarioDirty(false);
      const sessionProducts = (state.last_products as SimulationProduct[]) ?? [];
      setSimulationProducts(sessionProducts);
      setSelectedSimulationProductId(
        (state.last_product_id as string) ??
          (sessionProducts[0]?.id ?? null),
      );
      if (typeof window !== "undefined") {
        const payload = {
          scenario: state.last_query ?? "",
          products: sessionProducts,
          selected_product_id:
            (state.last_product_id as string) ?? sessionProducts[0]?.id ?? null,
          tone: "",
        };
        localStorage.setItem(
          simulationStorageKey,
          JSON.stringify(payload),
        );
        localStorage.setItem(
          simulationLatestStorageKey,
          JSON.stringify(payload),
        );
      }
      setPlan(undefined);
      setClarifications([]);
      setProductReasoning([]);
      const evidenceItems = state.last_research?.items ?? [];
      if (evidenceItems.length) {
        const evidenceProducts = evidenceItems.map((item: any) => ({
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
          state.last_research?.alignment?.per_item?.map((score) => ({
            product_id: score.product_id ?? "",
            score: score.score ?? 0,
            alignment_reasoning: score.alignment_reasoning,
          })) ?? [];
        const nextAnalysis: EvidenceAnalyzeResponse = {
          intent: state.last_intent as EvidenceAnalyzeResponse["intent"],
          goals: state.clarification_state?.extracted_goals ?? [],
          evidence_products: evidenceProducts,
          profiles: state.last_profiles ?? [],
          alignment_scores: alignmentScores,
        };
        setEvidenceAnalysis(nextAnalysis);
        if (typeof window !== "undefined") {
          localStorage.setItem(
            evidenceStorageKey,
            JSON.stringify({ analysis: nextAnalysis }),
          );
        }
        setEvidenceOptimization(null);
        setEvidenceVerification(null);
      } else {
        setEvidenceAnalysis(null);
        setEvidenceOptimization(null);
        setEvidenceVerification(null);
      }
      setSimulationTone("");
    },
    [
      clientId,
      evidenceStorageKey,
      setClientId,
      simulationLatestStorageKey,
      simulationStorageKey,
      userId,
    ],
  );

  useEffect(() => {
    if (!userId) return;
    const targetId = searchParams.get("session");
    if (targetId && targetId !== sessionId) {
      void handleSelectSession(targetId);
      return;
    }
    if (!targetId && !sessionId) {
      const lastId = localStorage.getItem(lastSessionKey);
      if (lastId) {
        void handleSelectSession(lastId);
      }
    }
  }, [handleSelectSession, lastSessionKey, searchParams, sessionId, userId]);

  const handleDeleteSession = useCallback(
    async (selectedId: string) => {
      if (!selectedId) return;
      setDeleteTargetId(selectedId);
    },
    [],
  );

  const handleOpenSimulation = useCallback(() => {
    if (typeof window === "undefined") return;
    const fallbackScenario = simulationScenario.trim() || lastQuery || "";
    const payload = {
      scenario: fallbackScenario,
      products: simulationProducts,
      selected_product_id: selectedSimulationProductId,
      tone: simulationTone,
    };
    localStorage.setItem(simulationStorageKey, JSON.stringify(payload));
    localStorage.setItem(
      simulationLatestStorageKey,
      JSON.stringify(payload),
    );
    const target = sessionId ? `/simulation?session=${sessionId}` : "/simulation";
    router.push(target);
  }, [
    lastQuery,
    router,
    selectedSimulationProductId,
    simulationProducts,
    simulationScenario,
    simulationStorageKey,
    simulationLatestStorageKey,
    simulationTone,
    sessionId,
  ]);

  const confirmDeleteSession = useCallback(async () => {
    if (!deleteTargetId) return;
    try {
      await deleteConversationSession(deleteTargetId, userId);
    } catch (error) {
      const message = (error as Error).message || "";
      if (!message.includes("API error 404")) {
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: `Error deleting conversation: ${(error as Error).message}` },
        ]);
        return;
      }
    } finally {
      updateSessions((current) =>
        current.filter((item) => item.id !== deleteTargetId),
      );
      if (deleteTargetId === sessionId) {
        resetConversation();
      }
      setDeleteTargetId(null);
    }
    },
    [deleteTargetId, resetConversation, sessionId, updateSessions, userId],
  );

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
      updateSessions((current) =>
        current.filter((item) => !sessionIds.includes(item.id)),
      );
      if (sessionId && sessionIds.includes(sessionId)) {
        resetConversation();
      }
      setDeleteTargetId(null);
    },
    [resetConversation, sessionId, updateSessions, userId],
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
      setSimulationRuns((current) =>
        current.filter((run) => !runIds.includes(run.id)),
      );
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
        onNewConversation={resetConversation}
        sessions={sessions}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
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
        activeSessionId={sessionId}
        onClose={handleCloseHistory}
        onSelect={(session) => {
          void handleSelectSession(session);
          setHistoryOpen(false);
        }}
        onSelectSimulation={(run) => {
          router.push(buildSimulationHref(run.id));
          setHistoryOpen(false);
        }}
        onSelectExperiment={(experiment) => {
          router.push(buildExperimentHref(experiment.id));
          setHistoryOpen(false);
        }}
        onRequestDelete={handleDeleteSession}
        onRequestDeleteSimulation={handleDeleteSimulationRun}
        onRequestDeleteExperiment={handleDeleteExperiment}
        onRequestDeleteSessionsBulk={handleBulkDeleteSessions}
        onRequestDeleteSimulationsBulk={handleBulkDeleteSimulations}
        onRequestDeleteExperimentsBulk={handleBulkDeleteExperiments}
      />
      <main className="main">
        <div className="main__content">
          <div className="main__toolbar">
            <button
              type="button"
              className="mobile-toggle"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
            >
              <span className="mobile-toggle__icon" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
            </button>
          </div>
          <div className="chat">
            <div className="chat__messages" ref={chatContainerRef}>
              <ChatWindow
                messages={messages}
                isThinking={isStreaming}
                thinkingMessage={thinkingMessage ?? undefined}
              />
            </div>
            {labOperator?.experiment_id || labOperator?.evidence ? (
              <div className="chat__lab-links">
                {labOperator?.experiment_id ? (
                  <button
                    type="button"
                    className="chat__quick-action"
                    onClick={() =>
                      router.push(buildExperimentHref(labOperator.experiment_id))
                    }
                  >
                    Open experiment
                  </button>
                ) : null}
                {Array.isArray(labOperator?.evidence?.runs) &&
                labOperator?.evidence?.runs?.[0]?.run_id ? (
                  <button
                    type="button"
                    className="chat__quick-action"
                    onClick={() =>
                      router.push(
                        buildSimulationHref(String(
                          (labOperator?.evidence as { runs?: { run_id?: unknown }[] } | null)
                            ?.runs?.[0]?.run_id ?? "",
                        )),
                      )
                    }
                  >
                    Open linked run
                  </button>
                ) : null}
              </div>
            ) : null}

            <form className="chat__input" onSubmit={handleSubmit}>
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="What are you looking for?"
                disabled={isStreaming}
                autoComplete="off"
                rows={3}
              />
              <div className="chat__input-row">
                <div className="chat__input-controls">
                  <select
                    value={chatModel}
                    onChange={(event) => {
                      const nextModel = event.target.value;
                      setChatModel(nextModel);
                      void applyChatModel(chatProvider, nextModel);
                    }}
                    aria-label="Model"
                    title="Model"
                  >
                    {(chatModelOptions.length ? chatModelOptions : [chatModel]).map(
                      (modelName) => (
                        <option key={modelName} value={modelName}>
                          {modelName}
                        </option>
                      ),
                    )}
                  </select>
                </div>
                <button
                  type={isStreaming ? "button" : "submit"}
                  className={`chat__send${isStreaming ? " chat__send--stop" : ""}`}
                  disabled={!inputValue.trim() && !isStreaming}
                  onClick={
                    isStreaming
                      ? () => {
                          abortRef.current?.abort();
                        }
                      : undefined
                  }
                >
                  {isStreaming ? (
                    <>
                      Stop
                      <span className="thinking-dots" aria-hidden="true">
                        <span>.</span>
                        <span>.</span>
                        <span>.</span>
                      </span>
                    </>
                  ) : (
                    "Send"
                  )}
                </button>
              </div>
            </form>
            {llmConfigError ? (
              <span className="chat__model-error">{llmConfigError}</span>
            ) : null}
          </div>
        </div>

        {hasInsights && (
          <aside className="insights">
            <IntentDisplay intent={intent} />
            <IntentionalityProfileCard
              product={plan?.products?.[0]}
              alignmentScore={plan?.alignment?.goal_alignment?.score}
              baselineScore={plan?.alignment?.goal_alignment?.baseline_score}
            />
            <GoalClarificationPanel state={goalState} />
            <ProductReasoning
              title="Research insights"
              products={researchResults}
              badge="Research"
              disclaimer="Research insights are synthesized from external sources; verify before purchase."
              actionLabel={researchRefreshing ? "Refreshing..." : "Refresh"}
              onAction={handleRefreshResearch}
              actionDisabled={researchRefreshing || !sessionId}
              onQuickCreateBattery={handleQuickCreateBattery}
              statusMessage={batteryStatus ?? backgroundStatus ?? researchStatus}
            />
            <div className="insights__summary">
              <div className="summary-card summary-card--header">
                <div className="summary-card__header">
                  <h4>Overview</h4>
                  <Link href="/overview" className="summary-card__link">
                    Open
                  </Link>
                </div>
                <p className="summary-card__text">
                  Jump to the full dashboard of simulation, evidence, and alignment signals.
                </p>
              </div>
              <div className="summary-card">
                <div className="summary-card__header">
                  <h4>Simulation Sandbox</h4>
                  <button
                    type="button"
                    className="summary-card__link"
                    onClick={handleOpenSimulation}
                  >
                    Open
                  </button>
                </div>
                <p className="summary-card__text">
                  {simulationScenario.trim() || lastQuery
                    ? `Scenario: ${simulationScenario.trim() || lastQuery}`
                    : "No scenario yet."}
              </p>
              <div className="summary-card__meta">
                <span>Runs: {simulationRuns.length}</span>
                <span>Lessons: {simulationLessons.length}</span>
                {typeof simulationRuns?.[0]?.protocol_readiness_score === "number" && (
                  <span>
                    <span
                      title="UCP readiness score based on business profile validation and platform capability intersection."
                    >
                      Protocol readiness: {simulationRuns[0].protocol_readiness_score}/100
                    </span>
                  </span>
                )}
              </div>
            </div>

              <div className="summary-card">
              <div className="summary-card__header">
                <h4>Evidence + Research</h4>
                <Link href="/evidence" className="summary-card__link">
                  Open
                </Link>
              </div>
              <div className="summary-card__badges">
                <Link href="/alignment#alignment-research" className="summary-card__badge">
                  Research
                </Link>
              </div>
              <p className="summary-card__text">
                {evidenceAnalysis?.evidence_products?.length
                  ? `${evidenceAnalysis.evidence_products.length} evidence items analyzed.`
                  : "No evidence analysis yet."}
                </p>
                <div className="summary-card__meta">
                  <span>
                    Lift:{" "}
                    {evidenceVerification?.lift !== undefined
                      ? `${Math.round(evidenceVerification.lift * 100)}%`
                      : "—"}
                  </span>
                  <span>Research: {researchResults?.length ?? 0}</span>
                </div>
              </div>

              <div className="summary-card">
                <div className="summary-card__header">
                  <h4>Alignment</h4>
                  <Link href="/alignment" className="summary-card__link">
                    Open
                  </Link>
                </div>
                <p className="summary-card__text">
                  {plan?.products?.length
                    ? `${plan.products.length} products scored.`
                    : "No alignment results yet."}
                </p>
                <div className="summary-card__meta">
                  <span>
                    Score:{" "}
                    {plan?.alignment?.goal_alignment?.score !== undefined
                      ? `${Math.round(plan.alignment.goal_alignment.score * 100)}%`
                      : "—"}
                  </span>
                  <span>Clarifications: {clarifications.length}</span>
                </div>
              </div>
            </div>
          </aside>
        )}
      </main>
    </div>
  );
}
