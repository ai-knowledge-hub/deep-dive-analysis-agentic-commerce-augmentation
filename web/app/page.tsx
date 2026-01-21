"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  analyzeEvidence,
  deleteConversationSession,
  getConversationSnapshot,
  listConversationSessions,
  optimizeRepresentation,
  refreshResearch,
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
} from "../lib/types";
import { ChatWindow, type Message } from "../components/chat/ChatWindow";
import { ProductReasoning } from "../components/products/ProductReasoning";
import { Sidebar } from "../components/layout/Sidebar";
import { GoalClarificationPanel } from "../components/values/GoalClarificationPanel";
import { IntentionalityProfileCard } from "../components/products/IntentionalityProfileCard";
import { IntentDisplay } from "../components/intent/IntentDisplay";
import { EvidencePanel } from "../components/evidence/EvidencePanel";
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
        setLastQuery(response.plan?.query ?? text);

        const analysis = await analyzeEvidence(text);
        setEvidenceAnalysis(analysis);
        const optimization = await optimizeRepresentation(
          analysis.evidence_products,
          text,
        );
        setEvidenceOptimization(optimization);
        const verification = await verifyRecommendation(
          text,
          analysis.evidence_products,
          optimization.optimized,
        );
        setEvidenceVerification(verification);
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
      setPlan(undefined);
      setClarifications([]);
      setProductReasoning([]);
      setEvidenceAnalysis(null);
      setEvidenceOptimization(null);
      setEvidenceVerification(null);
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
