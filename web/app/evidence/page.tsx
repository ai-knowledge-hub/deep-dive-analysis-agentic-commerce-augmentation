"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type { EvidenceAnalyzeResponse, SessionSummary } from "../../lib/types";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { EvidencePanel } from "../../components/evidence/EvidencePanel";
import {
  deleteConversationSession,
  getConversationSnapshot,
  listConversationSessions,
  listProductsByBrand,
} from "../../lib/api";
import { useTenant } from "../../components/tenant/TenantProvider";

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
  const [analysis, setAnalysis] = useState<EvidenceAnalyzeResponse | null>(null);
  const [optimization, setOptimization] = useState<null>(null);
  const [verification, setVerification] = useState<null>(null);
  const [targetCopy, setTargetCopy] = useState<string | null>(null);
  const [targetCopyUrl, setTargetCopyUrl] = useState<string | null>(null);
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
        localStorage.setItem(
          storageKey,
          JSON.stringify({ analysis: nextAnalysis }),
        );
      } catch (error) {
        console.warn("Failed to hydrate evidence from latest session", error);
      }
    };
    void loadFromLatestSession();
  }, [analysis, storageKey, userId]);

  useEffect(() => {
    if (!brandId || !productId || !userId) return;
    const loadTargetCopy = async () => {
      try {
        const response = await listProductsByBrand(brandId, userId);
        const product = response.products?.find((item) => item.id === productId);
        if (!product) return;
        const metadata = product.metadata ?? {};
        const creative = metadata.creative ?? {};
        const copy =
          creative.manual_copy ??
          creative.imported_copy ??
          product.description ??
          null;
        const url = creative.source_url ?? metadata.source_url ?? null;
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
            targetProductId={productId ?? undefined}
            targetProductName={productName ?? undefined}
            targetProductCopy={targetCopy ?? undefined}
            targetProductUrl={targetCopyUrl ?? undefined}
            onOpenSimulation={() => router.push("/simulation")}
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
