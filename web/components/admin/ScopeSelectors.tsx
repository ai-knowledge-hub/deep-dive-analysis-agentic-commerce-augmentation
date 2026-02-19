import type { AdminBrand, AdminClient, AdminProduct } from "../../lib/types";

type ScopeSelectorsProps = {
  activeClientId: string;
  activeBrandId: string;
  activeProductId: string;
  clients: AdminClient[];
  brands: AdminBrand[];
  products: AdminProduct[];
  onClientChange: (nextClientId: string) => void;
  onBrandChange: (nextBrandId: string) => void;
  onProductChange: (nextProductId: string) => void;
};

export function ScopeSelectors({
  activeClientId,
  activeBrandId,
  activeProductId,
  clients,
  brands,
  products,
  onClientChange,
  onBrandChange,
  onProductChange,
}: ScopeSelectorsProps) {
  return (
    <div className="admin-onboarding__scope">
      <div className="admin__selector">
        <label className="panel__label" htmlFor="admin-client-select">
          Scope client
        </label>
        <select
          id="admin-client-select"
          value={activeClientId}
          onChange={(event) => onClientChange(event.target.value)}
        >
          {clients.map((client) => (
            <option key={client.id} value={client.id}>
              {client.name}
            </option>
          ))}
        </select>
      </div>
      <div className="admin__selector">
        <label className="panel__label" htmlFor="admin-brand-select">
          Scope brand
        </label>
        <select
          id="admin-brand-select"
          value={activeBrandId}
          onChange={(event) => onBrandChange(event.target.value)}
          disabled={!activeClientId || brands.length === 0}
        >
          {brands.length === 0 ? <option value="">Select brand</option> : null}
          {brands.map((brand) => (
            <option key={brand.id} value={brand.id}>
              {brand.name}
            </option>
          ))}
        </select>
      </div>
      <div className="admin__selector">
        <label className="panel__label" htmlFor="admin-product-select">
          Scope product
        </label>
        <select
          id="admin-product-select"
          value={activeProductId}
          onChange={(event) => onProductChange(event.target.value)}
          disabled={!activeBrandId || products.length === 0}
        >
          {products.length === 0 ? <option value="">Select product</option> : null}
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
