"use client";

import React, { type ReactNode } from "react";
import type { AdminProduct } from "../../lib/types";

export type ProductCatalogForm = {
  id: string;
  name: string;
  description: string;
  productUrl: string;
};

type Props = {
  activeBrandId: string;
  selectedBrandName?: string | null;
  products: AdminProduct[];
  showCreateProduct: boolean;
  productForm: ProductCatalogForm;
  canCreateProduct: boolean;
  onShowCreateProductChange: (show: boolean) => void;
  onProductFormChange: (patch: Partial<ProductCatalogForm>) => void;
  onCreateProduct: () => void;
  children?: ReactNode;
};

export function ProductCatalogPanel({
  activeBrandId,
  selectedBrandName,
  products,
  showCreateProduct,
  productForm,
  canCreateProduct,
  onShowCreateProductChange,
  onProductFormChange,
  onCreateProduct,
  children,
}: Props) {
  return (
    <details>
      <summary>Product catalog</summary>
      {activeBrandId ? (
        <>
          <p className="panel__meta">
            Creates and edits products for brand: <strong>{selectedBrandName ?? activeBrandId}</strong>
          </p>
          {products.length === 0 ? (
            <p className="panel__empty">No products yet.</p>
          ) : (
            <ul className="admin__list">
              {products.map((product) => (
                <li key={product.id}>
                  <span>{product.name}</span>
                  <span className="admin__meta">{product.id}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="panel__actions">
            <button
              type="button"
              className="button button--ghost"
              onClick={() => onShowCreateProductChange(!showCreateProduct)}
            >
              {showCreateProduct ? "Hide create product form" : "Add new product"}
            </button>
          </div>
          {showCreateProduct ? (
            <div className="admin__form">
              <span className="panel__label">
                Create product for {selectedBrandName ?? activeBrandId}
              </span>
              <input
                type="text"
                placeholder="product-id"
                value={productForm.id}
                onChange={(event) => onProductFormChange({ id: event.target.value })}
                required
              />
              <input
                type="text"
                placeholder="Product name"
                value={productForm.name}
                onChange={(event) => onProductFormChange({ name: event.target.value })}
                required
              />
              <textarea
                rows={2}
                placeholder="Short description (required)"
                value={productForm.description}
                onChange={(event) => onProductFormChange({ description: event.target.value })}
                required
              />
              <input
                type="url"
                placeholder="Product URL (optional)"
                value={productForm.productUrl}
                onChange={(event) => onProductFormChange({ productUrl: event.target.value })}
              />
              <button
                type="button"
                className="button button--primary-subtle"
                onClick={onCreateProduct}
                disabled={!canCreateProduct}
              >
                Add product
              </button>
            </div>
          ) : null}
          {children}
        </>
      ) : (
        <p className="panel__empty">Select a brand first.</p>
      )}
    </details>
  );
}
