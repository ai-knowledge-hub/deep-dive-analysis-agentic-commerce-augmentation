import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ProductCatalogPanel } from "./ProductCatalogPanel";

describe("ProductCatalogPanel", () => {
  it("uses product key wording for product setup", async () => {
    const onProductFormChange = vi.fn();
    render(
      <ProductCatalogPanel
        activeBrandId="brand-a"
        selectedBrandName="Brand A"
        products={[]}
        showCreateProduct
        productForm={{ id: "", name: "", description: "", productUrl: "" }}
        canCreateProduct={false}
        onShowCreateProductChange={vi.fn()}
        onProductFormChange={onProductFormChange}
        onCreateProduct={vi.fn()}
      />,
    );

    await userEvent.type(screen.getByPlaceholderText("Product key"), "product-a");

    expect(onProductFormChange).toHaveBeenCalledWith({ id: "p" });
    expect(screen.queryByPlaceholderText("Product reference")).not.toBeInTheDocument();
  });
});
