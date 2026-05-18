"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { buildTenantStorageKey } from "../../lib/storage";

const LEGACY_DRAFT_KEY = "experiments_draft";

export function useExperimentDraft<TDraft>({
  userId,
  storageClientId,
  payload,
}: {
  userId: string | null;
  storageClientId?: string | null;
  payload: TDraft;
}) {
  const storageKey = useMemo(
    () => buildTenantStorageKey(LEGACY_DRAFT_KEY, userId, storageClientId ?? undefined),
    [storageClientId, userId],
  );
  const [restoreDraft, setRestoreDraft] = useState<TDraft | null>(null);
  const [showRestorePrompt, setShowRestorePrompt] = useState(false);
  const autosaveEnabled = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved =
      window.localStorage.getItem(storageKey) ?? window.localStorage.getItem(LEGACY_DRAFT_KEY);
    if (!saved) {
      autosaveEnabled.current = true;
      return;
    }
    try {
      setRestoreDraft(JSON.parse(saved) as TDraft);
      setShowRestorePrompt(true);
    } catch {
      window.localStorage.removeItem(storageKey);
      window.localStorage.removeItem(LEGACY_DRAFT_KEY);
      autosaveEnabled.current = true;
    }
  }, [storageKey]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!autosaveEnabled.current) return;
    window.localStorage.setItem(storageKey, JSON.stringify(payload));
  }, [payload, storageKey]);

  const markRestored = useCallback(() => {
    setShowRestorePrompt(false);
    autosaveEnabled.current = true;
  }, []);

  const dismissDraft = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(storageKey);
      window.localStorage.removeItem(LEGACY_DRAFT_KEY);
    }
    setRestoreDraft(null);
    setShowRestorePrompt(false);
    autosaveEnabled.current = true;
  }, [storageKey]);

  return {
    restoreDraft,
    showRestorePrompt,
    markRestored,
    dismissDraft,
  };
}
