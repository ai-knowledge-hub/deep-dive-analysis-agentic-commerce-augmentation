"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  analyzeEvidence,
  deleteConversationSession,
  getConversationSnapshot,
  listConversationSessions,
  optimizeRepresentation,
  refreshResearch,
  runSimulation,
  optimizeSimulation,
  retestSimulation,
  listSimulationRuns,
  getSimulationRun,
  requestBrandTone,
  updateSimulationTone,
  sendConversationMessage,
  startConversation,
  verifyRecommendation,
} from "../lib/api";
import type {
  ConversationResponse,
  EvidenceAnalyzeResponse,
  RepresentationOptimizeResponse,
  RecommendationVerifyResponse,
  SessionSummary,
  SimulationProduct,
  SimulationRunResponse,
  SimulationOptimizeResponse,
  SimulationRetestResponse,
  SimulationRunSummary,
} from "../lib/types";
import { ChatWindow, type Message } from "../components/chat/ChatWindow";
import { ProductReasoning } from "../components/products/ProductReasoning";
import { Sidebar } from "../components/layout/Sidebar";
import { GoalClarificationPanel } from "../components/values/GoalClarificationPanel";
import { IntentionalityProfileCard } from "../components/products/IntentionalityProfileCard";
import { IntentDisplay } from "../components/intent/IntentDisplay";
import { EvidencePanel } from "../components/evidence/EvidencePanel";
import { SimulationPanel } from "../components/simulation/SimulationPanel";
import { SimulationHistory } from "../components/simulation/SimulationHistory";
import { useUser } from "@clerk/nextjs";

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [plan, setPlan] = useState<ConversationResponse["plan"]>();
  const [clarifications, setClarifications] = useState<string[]>([]);
  const [productReasoning, setProductReasoning] = useState<
    ConversationResponse["product_explanations"]
  >([]);
  const [researchResults, setResearchResults] = useState<
    ConversationResponse["plan"]["research_results"]
  >([]);
  const [goalState, setGoalState] = useState<ConversationResponse["goal_state"]>();
  const [intent, setIntent] = useState<ConversationResponse["intent"]>();
  const [evidenceAnalysis, setEvidenceAnalysis] = useState<EvidenceAnalyzeResponse | null>(null);
  const [evidenceOptimization, setEvidenceOptimization] =
    useState<RepresentationOptimizeResponse | null>(null);
  const [evidenceVerification, setEvidenceVerification] =
    useState<RecommendationVerifyResponse | null>(null);
  const [simulationRun, setSimulationRun] = useState<SimulationRunResponse | null>(null);
  const [simulationOptimized, setSimulationOptimized] =
    useState<SimulationOptimizeResponse | null>(null);
  const [simulationRetest, setSimulationRetest] =
    useState<SimulationRetestResponse | null>(null);
  const [simulationScenario, setSimulationScenario] = useState("");
  const [simulationToneSuggestion, setSimulationToneSuggestion] = useState<string | null>(null);
  const [simulationTone, setSimulationTone] = useState("");
  const [simulationToneNotice, setSimulationToneNotice] = useState<string | null>(null);
  const [simulationProducts, setSimulationProducts] = useState<SimulationProduct[]>([]);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationRuns, setSimulationRuns] = useState<SimulationRunSummary[]>([]);
  const [selectedSimulationProductId, setSelectedSimulationProductId] =
    useState<string | null>(null);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [researchLoading, setResearchLoading] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const { user } = useUser();
  const userId = user?.id ?? null;
  const storageKey = useMemo(
    () => (userId ? `intentionality.sessions.${userId}` : "intentionality.sessions.anonymous"),
    [userId],
  );

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

  const handleCloseHistory = useCallback(() => {
    if (isHistoryClosing) return;
    setHistoryClosing(true);
    window.setTimeout(() => {
      setHistoryOpen(false);
      setHistoryClosing(false);
    }, 200);
  }, [isHistoryClosing]);

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
    setSimulationRun(null);
    setSimulationOptimized(null);
    setSimulationRetest(null);
    setSimulationProducts([]);
    setSelectedSimulationProductId(null);
    setSimulationToneSuggestion(null);
    setSimulationTone("");
  }, []);

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
    async (text: string) => {
      if (!text.trim()) return;
      setMessages((prev) => [...prev, { role: "user", content: text }]);
      setLoading(true);
      try {
        let response: ConversationResponse;
        if (!sessionId) {
          response = await startConversation(text, userId);
          setSessionId(response.session_id);
          upsertSession({
            id: response.session_id,
            preview: text,
            created_at: response.snapshot?.session?.created_at,
            last_turn_at: new Date().toISOString(),
          });
        } else {
          response = await sendConversationMessage(sessionId, text, userId);
          upsertSession({
            id: sessionId,
            preview: text,
            created_at: response.snapshot?.session?.created_at,
            last_turn_at: new Date().toISOString(),
          });
        }

        const clarification = response.clarification;
        if (clarification) {
          setMessages((prev) => [...prev, { role: "agent", content: clarification }]);
        }

        if (response.explanation) {
          setMessages((prev) => [...prev, { role: "agent", content: response.explanation! }]);
        }
        setPlan(response.plan);
        setClarifications(response.plan?.clarifications ?? []);
        setProductReasoning(response.product_explanations ?? []);
        setGoalState(response.goal_state);
        setIntent(response.intent);
        setResearchResults(response.plan?.research_results ?? []);
        const nextQuery = response.plan?.query ?? text;
        setLastQuery(nextQuery);
        setSimulationScenario((prev) => (prev.trim() ? prev : nextQuery));

        const analysis = await analyzeEvidence(text);
        setEvidenceAnalysis(analysis);
        const optimization = await optimizeRepresentation(
          analysis.evidence_products,
          text,
          simulationTone || undefined,
        );
        setEvidenceOptimization(optimization);
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
        setMessages((prev) => [...prev, { role: "agent", content: `Error: ${(error as Error).message}` }]);
      } finally {
        setLoading(false);
      }
    },
    [sessionId, upsertSession, userId],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      void sendMessage(inputValue);
      setInputValue("");
    }
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim()) {
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
    void listSimulationRuns(userId).then((response) => {
      setSimulationRuns(response.runs ?? []);
    });
  }, [userId]);

  useEffect(() => {
    const suggestion = simulationRun?.result?.tone?.summary ?? null;
    setSimulationToneSuggestion(suggestion);
    if (suggestion && !simulationTone) {
      setSimulationTone(suggestion);
    }
  }, [simulationRun, simulationTone]);

  const handleSelectSession = useCallback(
    async (selectedId: string) => {
      if (!selectedId) return;
      const snapshot = await getConversationSnapshot(selectedId, userId);
      const turns = snapshot.snapshot?.turns ?? [];
      setSessionId(selectedId);
      setMessages(
        turns.map((turn) => ({
          role: turn.speaker,
          content: turn.content,
        })),
      );
      const state = snapshot.snapshot?.session?.state ?? {};
      setGoalState(state.clarification_state as ConversationResponse["goal_state"]);
      setIntent(state.last_intent as ConversationResponse["intent"]);
      setResearchResults(state.last_research?.items ?? []);
      setLastQuery(state.last_query ?? null);
      setSimulationScenario(state.last_query ?? "");
      setPlan(undefined);
      setClarifications([]);
      setProductReasoning([]);
      setEvidenceAnalysis(null);
      setEvidenceOptimization(null);
      setEvidenceVerification(null);
      setSimulationRun(null);
      setSimulationOptimized(null);
      setSimulationRetest(null);
      setSimulationProducts([]);
      setSelectedSimulationProductId(null);
      setSimulationToneSuggestion(null);
      setSimulationTone("");
    },
    [userId],
  );

  const handleDeleteSession = useCallback(
    async (selectedId: string) => {
      if (!selectedId) return;
      setDeleteTargetId(selectedId);
    },
    [],
  );

  const confirmDeleteSession = useCallback(async () => {
    if (!deleteTargetId) return;
      try {
        await deleteConversationSession(deleteTargetId, userId);
        updateSessions((current) =>
          current.filter((item) => item.id !== deleteTargetId),
        );
        if (deleteTargetId === sessionId) {
          resetConversation();
        }
      } catch (error) {
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: `Error deleting conversation: ${(error as Error).message}` },
        ]);
      } finally {
        setDeleteTargetId(null);
      }
    },
    [deleteTargetId, resetConversation, sessionId, updateSessions, userId],
  );

  const handleRefreshResearch = useCallback(async () => {
    if (!sessionId) return;
    setResearchLoading(true);
    try {
      const response = await refreshResearch(sessionId, userId, lastQuery ?? undefined);
      setResearchResults(response.research_results ?? []);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: `Error refreshing research: ${(error as Error).message}` },
      ]);
    } finally {
      setResearchLoading(false);
    }
  }, [lastQuery, sessionId, userId]);

  const handleRunSimulation = useCallback(async () => {
    if (!simulationScenario.trim() && !lastQuery) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: "Add a scenario before running a simulation." },
      ]);
      return;
    }
    if (simulationProducts.length === 0) {
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: "Add a scenario and evidence products before running a simulation.",
        },
      ]);
      return;
    }
    setSimulationLoading(true);
    try {
      const scenario = simulationScenario.trim() || lastQuery;
      const response = await runSimulation(
        scenario,
        simulationProducts,
        userId,
        sessionId,
      );
      setSimulationRun(response);
      setSimulationOptimized(null);
      setSimulationRetest(null);
      setSimulationToneSuggestion(response.result?.tone?.summary ?? null);
      if (!simulationTone) {
        setSimulationTone(response.result?.tone?.summary ?? "");
      }
      void listSimulationRuns(userId).then((runs) =>
        setSimulationRuns(runs.runs ?? []),
      );
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: `Error running simulation: ${(error as Error).message}` },
      ]);
    } finally {
      setSimulationLoading(false);
    }
  }, [lastQuery, sessionId, simulationProducts, simulationScenario, simulationTone, userId]);

  const handleOptimizeSimulation = useCallback(async (productId?: string) => {
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
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: `Error optimizing simulation: ${(error as Error).message}` },
      ]);
    } finally {
      setSimulationLoading(false);
    }
  }, [simulationRun, simulationTone, userId]);

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
      const response = await retestSimulation(
        simulationRun.run_id,
        updated,
        userId,
      );
      setSimulationRetest(response);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: `Error retesting simulation: ${(error as Error).message}` },
      ]);
    } finally {
      setSimulationLoading(false);
    }
  }, [simulationOptimized, simulationProducts, simulationRun, userId]);

  const handleSelectSimulationRun = useCallback(
    async (runId: string) => {
      try {
        const response = await getSimulationRun(runId, userId);
        const run = response.run;
        setSimulationRun({ run_id: run.id, result: run.result });
        setSimulationOptimized(null);
        setSimulationRetest(run.retest ? { run_id: run.id, result: run.retest } : null);
        setSimulationProducts(run.products ?? []);
        setSimulationScenario(run.query ?? "");
        const scenario = (run.scenario as Record<string, unknown> | undefined) || {};
        const confirmedTone = (scenario.confirmed_tone as string | undefined) ?? "";
        const suggestedTone = (scenario.tone_suggestion as string | undefined) ?? null;
        setSimulationToneSuggestion(run.result?.tone?.summary ?? suggestedTone ?? null);
        setSimulationTone(confirmedTone || run.result?.tone?.summary || "");
        if (run.products?.length) {
          setSelectedSimulationProductId(run.products[0].id);
        }
      } catch (error) {
        setMessages((prev) => [
          ...prev,
          { role: "agent", content: `Error loading simulation: ${(error as Error).message}` },
        ]);
      }
    },
    [userId],
  );

  const handleSaveTone = useCallback(async () => {
    if (!simulationRun) return;
    try {
      await updateSimulationTone(simulationRun.run_id, simulationTone, userId);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: `Error saving tone: ${(error as Error).message}` },
      ]);
    }
  }, [simulationRun, simulationTone, userId]);

  const handleClearTone = useCallback(async () => {
    setSimulationTone("");
    if (!simulationRun) return;
    try {
      await updateSimulationTone(simulationRun.run_id, "", userId);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: `Error saving tone: ${(error as Error).message}` },
      ]);
    }
  }, [simulationRun, userId]);

  const handleToneFromBrand = useCallback(async () => {
    try {
      const response = await requestBrandTone(simulationRun?.run_id, userId);
      setSimulationToneNotice(response.message);
      window.setTimeout(() => setSimulationToneNotice(null), 2600);
    } catch (error) {
      setSimulationToneNotice("Brand tone import is not ready yet.");
    }
  }, [simulationRun, userId]);

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
      {isHistoryOpen && (
        <div
          className={`history-overlay ${isHistoryClosing ? "is-closing" : ""}`}
          role="dialog"
          aria-modal="true"
          onClick={() => handleCloseHistory()}
        >
          <div
            className={`history-panel ${isHistoryClosing ? "is-closing" : ""}`}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="history-panel__header">
              <h4>History</h4>
              <button
                type="button"
                className="history-panel__close"
                onClick={() => handleCloseHistory()}
                aria-label="Close history"
              >
                ×
              </button>
            </div>
            <div className="history-panel__list">
              {sessions.length === 0 ? (
                <p className="panel__empty">No conversations yet.</p>
              ) : (
                sessions.map((session) => (
                  <button
                    key={session.id}
                    type="button"
                    className={`history-panel__item ${
                      session.id === sessionId ? "is-active" : ""
                    }`}
                    onClick={() => {
                      void handleSelectSession(session.id);
                      setHistoryOpen(false);
                    }}
                  >
                    <div className="history-panel__row">
                      <span
                        className="history-panel__title"
                        title={session.preview || "Conversation"}
                      >
                        {session.preview || "Conversation"}
                      </span>
                      <button
                        type="button"
                        className="history-panel__delete"
                        onClick={(event) => {
                          event.stopPropagation();
                          handleDeleteSession(session.id);
                        }}
                        aria-label="Delete conversation"
                        title="Delete conversation"
                      >
                        <svg
                          viewBox="0 0 24 24"
                          aria-hidden="true"
                          className="icon"
                        >
                          <path
                            d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9z"
                            fill="currentColor"
                          />
                        </svg>
                      </button>
                    </div>
                    {session.last_turn_at && (
                      <span className="history-panel__meta">
                        {new Date(session.last_turn_at).toLocaleDateString()}
                      </span>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
      <main className="main">
        <div className="main__content">
          <div className="main__toolbar">
            <button
              type="button"
              className="mobile-toggle"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
            >
              Menu
            </button>
          </div>
          <div className="chat">
            <div className="chat__messages" ref={chatContainerRef}>
              <ChatWindow messages={messages} />
            </div>

            <form className="chat__input" onSubmit={handleSubmit}>
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="What are you looking for?"
                disabled={loading}
                autoComplete="off"
                rows={1}
              />
              <button
                type="submit"
                className="chat__send"
                disabled={loading || !inputValue.trim()}
              >
                {loading ? "..." : "Send"}
              </button>
            </form>
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
            <EvidencePanel
              analysis={evidenceAnalysis}
              optimization={evidenceOptimization}
              verification={evidenceVerification}
            />
            <SimulationPanel
              query={lastQuery}
              scenarioValue={simulationScenario}
              onScenarioChange={setSimulationScenario}
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
              canRun={Boolean((simulationScenario.trim() || lastQuery) && simulationProducts.length > 0)}
              canOptimize={Boolean(simulationRun?.result?.gap_analysis?.length)}
              canRetest={Boolean(simulationRun && simulationOptimized)}
              onRun={handleRunSimulation}
              onOptimize={handleOptimizeSimulation}
              onRetest={handleRetestSimulation}
              onSelectProduct={setSelectedSimulationProductId}
            />
            <SimulationHistory
              runs={simulationRuns}
              activeRunId={simulationRun?.run_id}
              onSelect={handleSelectSimulationRun}
            />
            <ProductReasoning
              title="Catalog Recommendations"
              products={plan?.catalog_results ?? plan?.products}
              explanations={productReasoning}
            />
            <ProductReasoning
              title="Research Insights"
              badge="Research"
              products={researchResults}
              actionLabel="Refresh"
              onAction={handleRefreshResearch}
              actionDisabled={researchLoading}
              disclaimer="Synthesized findings from external sources; verify details before purchasing."
            />
          </aside>
        )}
      </main>
    </div>
  );
}
