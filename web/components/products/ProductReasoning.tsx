"use client";

import type { ConversationResponse, Product } from "../../lib/types";

type ProductExplanation = NonNullable<ConversationResponse["product_explanations"]>[number];

type Props = {
  products?: Product[];
  explanations?: ProductExplanation[];
};

function mergeProducts(products?: Product[], explanations?: ProductExplanation[]) {
  const explanationEntries = new Map<string, ProductExplanation>();
  explanations?.forEach((item, index) => {
    const key = item.id ?? item.name ?? `explanation-${index}`;
    explanationEntries.set(key, item);
  });

  const merged = (products ?? []).map((product, index) => {
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
      capabilities_enabled: product.capabilities_enabled ?? explanation?.capabilities_enabled,
      reasoning: product.reasoning ?? explanation?.reasoning,
    };
  });

  const remaining = Array.from(explanationEntries.values()).map((explanation, index) => ({
    id: explanation.id ?? `extra-${index}`,
    name: explanation.name ?? "Empowerment action",
    confidence: explanation.confidence,
    capabilities_enabled: explanation.capabilities_enabled,
    reasoning: explanation.reasoning,
  }));

  return [...merged, ...remaining];
}

export function ProductReasoning({ products, explanations }: Props) {
  const merged = mergeProducts(products, explanations);

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h3>Recommendations</h3>
        {merged.length > 0 && (
          <span className="panel__badge">{merged.length}</span>
        )}
      </div>

      {merged.length === 0 ? (
        <p className="panel__empty">No recommendations yet.</p>
      ) : (
        <div className="products">
          {merged.map((product) => (
            <div key={product.id} className="product">
              <div className="product__header">
                <span className="product__name">{product.name}</span>
                {product.confidence !== undefined && (
                  <span className="product__confidence">
                    {(product.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              {(product.capabilities_enabled ?? []).length > 0 && (
                <div className="product__tags">
                  {(product.capabilities_enabled ?? []).slice(0, 3).map((cap, i) => (
                    <span key={i} className="product__tag">{cap}</span>
                  ))}
                </div>
              )}
              <p className="product__reasoning">
                {product.reasoning ?? "Reasoning pending..."}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
