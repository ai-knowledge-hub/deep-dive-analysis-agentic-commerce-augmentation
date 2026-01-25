"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type { ConversationResponse, SessionSummary } from "../../lib/types";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { IntentDisplay } from "../../components/intent/IntentDisplay";
import { IntentionalityProfileCard } from "../../components/products/IntentionalityProfileCard";
import { GoalClarificationPanel } from "../../components/values/GoalClarificationPanel";
import { ProductReasoning } from "../../components/products/ProductReasoning";
import { deleteConversationSession, listConversationSessions } from "../../lib/api";

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
  const [snapshot, setSnapshot] = useState<AlignmentSnapshot>({});
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

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
  }, [userId]);

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

  const plan = snapshot.plan;
  const products = plan?.products ?? [];
  const research = snapshot.research_results ?? plan?.research_results ?? [];

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
            <ProductReasoning
              title="Catalog recommendations"
              products={plan?.products ?? []}
              explanations={snapshot.product_reasoning}
              badge={snapshot.last_query ? "Catalog" : undefined}
              disclaimer="Catalog results reflect product data currently available in the source feed."
            />
            <div id="alignment-research">
              <ProductReasoning
                title="Research insights"
                products={research}
                badge="Research"
                disclaimer="Research insights are synthesized from external sources; verify before purchase."
              />
            </div>
          </div>

          <div className="detail__note">
            Alignment data reflects the latest chat session. Ask a new question to update.
          </div>
        </div>
      </main>
    </div>
  );
}
