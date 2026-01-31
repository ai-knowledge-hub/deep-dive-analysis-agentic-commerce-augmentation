"use client";

import type { ConversationResponse, Product } from "../../lib/types";

type ProductExplanation = NonNullable<ConversationResponse["product_explanations"]>[number];

type Props = {
  products?: Product[];
  explanations?: ProductExplanation[];
  title?: string;
  badge?: string;
  disclaimer?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionDisabled?: boolean;
  onQuickCreateBattery?: (productId: string, productName?: string) => void;
  statusMessage?: string | null;
};

type MergedProduct = {
  id: string;
  name: string;
  confidence?: number;
  alignment_score?: number;
  alignment_reasoning?: string;
  low_confidence?: boolean;
  capabilities_enabled?: string[];
  description?: string;
  reasoning?: string;
  offer_url?: string;
};

function mergeProducts(products?: Product[], explanations?: ProductExplanation[]) {
  const explanationEntries = new Map<string, ProductExplanation>();
  explanations?.forEach((item, index) => {
    const key = item.id ?? item.name ?? `explanation-${index}`;
    explanationEntries.set(key, item);
  });

  const merged: MergedProduct[] = (products ?? []).map((product, index) => {
    let matchedKey: string | undefined;
    if (product.id && explanationEntries.has(product.id)) {
      matchedKey = product.id;
    } else if (product.name) {
      for (const [key, explanation] of explanationEntries.entries()) {
        if (explanation.name === product.name) {
          matchedKey = key;
          break;
        }
      }
    }

    const explanation = matchedKey ? explanationEntries.get(matchedKey) : undefined;
    if (matchedKey) {
      explanationEntries.delete(matchedKey);
    }

    return {
      id: product.id ?? explanation?.id ?? `product-${index}`,
      name: product.name ?? explanation?.name ?? "Recommendation",
      confidence: product.confidence ?? explanation?.confidence,
      alignment_score: product.alignment_score,
      alignment_reasoning: product.alignment_reasoning,
      low_confidence: product.low_confidence,
      capabilities_enabled: product.capabilities_enabled ?? explanation?.capabilities_enabled,
      description: product.description,
      reasoning: product.reasoning ?? explanation?.reasoning,
      offer_url: product.offer_url,
    };
  });

  const remaining: MergedProduct[] = Array.from(explanationEntries.values()).map((explanation, index) => ({
    id: explanation.id ?? `extra-${index}`,
    name: explanation.name ?? "Recommendation",
    confidence: explanation.confidence,
    capabilities_enabled: explanation.capabilities_enabled,
    reasoning: explanation.reasoning,
    offer_url: undefined,
  }));

  return [...merged, ...remaining];
}

export function ProductReasoning({
  products,
  explanations,
  title = "Recommendations",
  badge,
  disclaimer,
  actionLabel,
  onAction,
  actionDisabled,
  onQuickCreateBattery,
  statusMessage,
}: Props) {
  const merged = mergeProducts(products, explanations);

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h3>{title}</h3>
        <div className="panel__meta">
          {actionLabel && (
            <button
              type="button"
              className="panel__action"
              onClick={onAction}
              disabled={actionDisabled}
            >
              {actionLabel}
            </button>
          )}
          {badge && <span className="panel__badge panel__badge--info">{badge}</span>}
          {merged.length > 0 && (
            <span className="panel__badge">{merged.length}</span>
          )}
        </div>
      </div>
      {statusMessage ? <p className="panel__success">{statusMessage}</p> : null}

      {merged.length === 0 ? (
        <p className="panel__empty">No recommendations yet.</p>
      ) : (
        <div className="products">
          {merged.map((product) => (
            <div key={product.id} className="product">
              <div className="product__header">
                <span className="product__name">{product.name}</span>
                <div className="product__meta">
                  {onQuickCreateBattery && product.id ? (
                    <button
                      type="button"
                      className="product__action"
                      onClick={() => onQuickCreateBattery(product.id, product.name)}
                    >
                      Create battery
                    </button>
                  ) : null}
                  {product.alignment_score !== undefined && (
                    <span
                      className="product__confidence product__tooltip"
                      data-tooltip="Alignment score: how well the product matches the inferred goals."
                    >
                      Align {(product.alignment_score * 100).toFixed(0)}%
                    </span>
                  )}
                  {product.low_confidence && (
                    <span className="product__flag">Low confidence</span>
                  )}
                  {product.confidence !== undefined && (
                    <span
                      className="product__confidence product__tooltip"
                      data-tooltip="Confidence: quality/coverage of the product data source."
                    >
                      {(product.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
              {(product.capabilities_enabled ?? []).length > 0 && (
                <div className="product__tags">
                  {(product.capabilities_enabled ?? []).slice(0, 3).map((cap, i) => (
                    <span key={i} className="product__tag">{cap}</span>
                  ))}
                </div>
              )}
              <p className="product__reasoning">
                {product.reasoning ??
                  product.alignment_reasoning ??
                  product.description ??
                  "Reasoning pending..."}
              </p>
              {product.offer_url ? (
                <a
                  className="product__link"
                  href={product.offer_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  View source
                </a>
              ) : null}
              {product.alignment_reasoning && product.reasoning ? (
                <p className="product__alignment">
                  {product.alignment_reasoning}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )}
      {disclaimer ? <p className="panel__disclaimer">{disclaimer}</p> : null}
    </div>
  );
}
