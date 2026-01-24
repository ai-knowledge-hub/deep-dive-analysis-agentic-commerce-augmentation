"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  EvidenceAnalyzeResponse,
  RecommendationVerifyResponse,
  RepresentationOptimizeResponse,
  SessionSummary,
} from "../../lib/types";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { EvidencePanel } from "../../components/evidence/EvidencePanel";
import { deleteConversationSession, listConversationSessions } from "../../lib/api";

export default function EvidencePage() {
  const router = useRouter();
  const { user } = useUser();
  const userId = user?.id ?? null;
  const storageKey = useMemo(
    () => (userId ? `intentionality.evidence.${userId}` : "intentionality.evidence.anonymous"),
    [userId],
  );
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [analysis, setAnalysis] = useState<EvidenceAnalyzeResponse | null>(null);
  const [optimization, setOptimization] = useState<RepresentationOptimizeResponse | null>(null);
  const [verification, setVerification] = useState<RecommendationVerifyResponse | null>(null);
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
      setOptimization((payload.optimization as RepresentationOptimizeResponse) ?? null);
      setVerification((payload.verification as RecommendationVerifyResponse) ?? null);
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
            title="Evidence Discovery"
            subtitle="Review the latest evidence analysis and optimized representation."
            onMenu={() => setSidebarOpen(true)}
            onBack={() => router.push("/")}
          />
          <EvidencePanel
            analysis={analysis}
            optimization={optimization}
            verification={verification}
          />
          <div className="detail__note">
            Evidence runs sync from the latest chat query. Run a new query to refresh.
          </div>
        </div>
      </main>
    </div>
  );
}
