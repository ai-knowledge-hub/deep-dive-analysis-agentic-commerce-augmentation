"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  AdminProduct,
  AudienceSegment,
  QueryBattery,
  QueryBatteryMetrics,
  QueryBatteryQuery,
} from "../../lib/types";
import {
  getBatteryMetrics,
  listBatteryAudienceSegments,
  listBatteryQueries,
} from "../../lib/api";

type Args = {
  batteries: QueryBattery[];
  selectedBatteryId: string;
  fallbackBatteryId?: string | null;
  productDetail?: AdminProduct | null;
  userId: string | null;
};

export function useExperimentBatteryReadModels({
  batteries,
  selectedBatteryId,
  fallbackBatteryId,
  productDetail,
  userId,
}: Args) {
  const [queries, setQueries] = useState<QueryBatteryQuery[]>([]);
  const [batteryMetrics, setBatteryMetrics] = useState<QueryBatteryMetrics | null>(null);
  const [audienceSegments, setAudienceSegments] = useState<AudienceSegment[]>([]);
  const [audienceSegmentsStatus, setAudienceSegmentsStatus] = useState<string | null>(null);

  const queryMap = useMemo(() => {
    const map = new Map<string, string>();
    queries.forEach((query) => map.set(query.id, query.query_text));
    return map;
  }, [queries]);

  const selectedBattery = useMemo(
    () => batteries.find((battery) => battery.id === selectedBatteryId) ?? null,
    [batteries, selectedBatteryId],
  );

  const hasBottomUpMetadata = useMemo(() => {
    const metadata = productDetail?.metadata ?? {};
    const canonicalSpec =
      (metadata.canonical_intent_spec as Record<string, unknown> | undefined) ?? {};
    const features = metadata.features;
    const useCase = metadata.use_case ?? metadata.scenario;
    const hasFeatures =
      (Array.isArray(features) && features.length > 0) ||
      (typeof features === "string" && features.trim() !== "");
    const hasUseCase =
      (Array.isArray(useCase) && useCase.length > 0) ||
      (typeof useCase === "string" && useCase.trim() !== "");
    const canonicalFeatures = canonicalSpec.feature_concepts;
    const canonicalUseCases = canonicalSpec.use_cases;
    const hasCanonicalFeatures =
      (Array.isArray(canonicalFeatures) && canonicalFeatures.length > 0) ||
      (typeof canonicalFeatures === "string" && canonicalFeatures.trim() !== "");
    const hasCanonicalUseCases =
      (Array.isArray(canonicalUseCases) && canonicalUseCases.length > 0) ||
      (typeof canonicalUseCases === "string" && canonicalUseCases.trim() !== "");
    const hasIntentLabels = Boolean(metadata.intent_labels || metadata.intent_archetypes);
    const hasVertical = Boolean(
      metadata.vertical ||
        metadata.domain ||
        metadata.category ||
        canonicalSpec.category,
    );
    return (
      hasFeatures ||
      hasUseCase ||
      hasCanonicalFeatures ||
      hasCanonicalUseCases ||
      hasIntentLabels ||
      hasVertical
    );
  }, [productDetail]);

  useEffect(() => {
    const batteryId = selectedBatteryId || fallbackBatteryId;
    if (batteryId) {
      void listBatteryQueries(batteryId, userId).then((response) => {
        setQueries(response.queries ?? []);
      });
      void getBatteryMetrics(batteryId, userId).then((response) => {
        setBatteryMetrics(response.metrics ?? null);
      });
    } else {
      setQueries([]);
      setBatteryMetrics(null);
    }
  }, [fallbackBatteryId, selectedBatteryId, userId]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedBattery) {
      setAudienceSegments([]);
      setAudienceSegmentsStatus(null);
      return;
    }
    void listBatteryAudienceSegments(selectedBattery.id, userId)
      .then((response) => {
        if (cancelled) return;
        setAudienceSegments(response.segments ?? []);
      })
      .catch(() => {
        if (cancelled) return;
        setAudienceSegments([]);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedBattery, userId]);

  return {
    queries,
    setQueries,
    queryMap,
    selectedBattery,
    batteryMetrics,
    audienceSegments,
    setAudienceSegments,
    audienceSegmentsStatus,
    setAudienceSegmentsStatus,
    hasBottomUpMetadata,
  };
}
