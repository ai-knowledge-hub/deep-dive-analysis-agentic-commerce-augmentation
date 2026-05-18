"use client";

import { useEffect, useState } from "react";
import { getLatestBrandBelief, listAdminProducts, listBrandBeliefs } from "../../lib/api";
import type { AdminProduct, BrandBelief } from "../../lib/types";

export function useExperimentContextData({
  brandId,
  productId,
  userId,
}: {
  brandId?: string | null;
  productId?: string | null;
  userId: string | null;
}) {
  const [productDetail, setProductDetail] = useState<AdminProduct | null>(null);
  const [beliefCount, setBeliefCount] = useState<number>(0);
  const [latestBelief, setLatestBelief] = useState<BrandBelief | null>(null);

  useEffect(() => {
    if (!brandId || !productId || !userId) {
      setProductDetail(null);
      return;
    }
    let active = true;
    listAdminProducts(brandId, userId)
      .then((response) => {
        if (!active) return;
        const match = (response.products ?? []).find((product) => product.id === productId);
        setProductDetail(match ?? null);
      })
      .catch(() => {
        if (!active) return;
        setProductDetail(null);
      });
    return () => {
      active = false;
    };
  }, [brandId, productId, userId]);

  useEffect(() => {
    if (!brandId) {
      setBeliefCount(0);
      setLatestBelief(null);
      return;
    }
    void listBrandBeliefs(brandId, userId, 25)
      .then((response) => {
        setBeliefCount((response.beliefs ?? []).length);
      })
      .catch(() => setBeliefCount(0));
    void getLatestBrandBelief(brandId, userId)
      .then((response) => {
        setLatestBelief(response.belief ?? null);
      })
      .catch(() => setLatestBelief(null));
  }, [brandId, userId]);

  return { productDetail, beliefCount, latestBelief };
}
