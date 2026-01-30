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

  const loadDemoData = useCallback(async () => {
    try {
      // Load demo data from the JSON file
      const response = await fetch('/data/evidence_demo.json');
      const demoProducts = await response.json();

      // Transform demo data into expected format
      const demoAnalysis: EvidenceAnalyzeResponse = {
        goals: ["Find products that work well in bright rooms", "Improve work-from-home comfort"],
        evidence_products: demoProducts.map((product: any) => ({
          id: product.id,
          name: product.name,
          description: product.description,
          source: product.source,
          url: product.url,
          price: product.price,
          confidence: product.confidence,
          metadata: {},
        })),
        profiles: demoProducts.map((product: any) => ({
          product_id: product.id,
          capabilities_enabled: ["anti-glare", "high-brightness"],
          goals_served: ["bright room viewing"],
          outcomes_expected: ["clear picture in daylight"],
        })),
        alignment_scores: demoProducts.map((product: any) => ({
          product_id: product.id,
          score: product.confidence,
          confidence: product.confidence,
        })),
      };

      const demoOptimization: RepresentationOptimizeResponse = {
        goals: ["Find products that work well in bright rooms", "Improve work-from-home comfort"],
        optimized: demoProducts.map((product: any) => ({
          id: product.id,
          name: product.name,
          before: product.description,
          after: product.optimized_description,
          capabilities: ["outcome-focused language", "intent alignment"],
          outcomes: ["improved discoverability"],
          goals: ["bright room viewing"],
        })),
        alignment_deltas: demoProducts.map((product: any) => ({
          product_id: product.id,
          before: product.confidence * 0.7,
          after: product.confidence,
          delta: product.confidence * 0.3,
        })),
      };

      const demoVerification: RecommendationVerifyResponse = {
        goals: ["Find products that work well in bright rooms", "Improve work-from-home comfort"],
        predicted: demoProducts.slice(0, 3).map((p: any) => p.id),
        actual: demoProducts.map((p: any) => p.id),
        lift: (demoProducts.length - 3) / 3,
        baseline_alignment: demoProducts.slice(0, 3).map((product: any) => ({
          product_id: product.id,
          score: product.confidence * 0.7,
        })),
        optimized_alignment: demoProducts.map((product: any) => ({
          product_id: product.id,
          score: product.confidence,
        })),
      };

      setAnalysis(demoAnalysis);
      setOptimization(demoOptimization);
      setVerification(demoVerification);

      // Save to local storage
      if (typeof window !== "undefined") {
        localStorage.setItem(
          storageKey,
          JSON.stringify({
            analysis: demoAnalysis,
            optimization: demoOptimization,
            verification: demoVerification,
          })
        );
      }
    } catch (error) {
      console.error('Failed to load demo data:', error);
    }
  }, [storageKey]);

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
            onLoadDemo={loadDemoData}
          />
          <div className="detail__note">
            Evidence runs sync from the latest chat query. Run a new query to refresh.
          </div>
        </div>
      </main>
    </div>
  );
}
