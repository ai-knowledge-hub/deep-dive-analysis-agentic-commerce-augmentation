"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useUser } from "@clerk/nextjs";

import { listAdminBrands, listAdminClients, listAdminProducts } from "../../lib/api";

type TenantProduct = {
  id: string;
  name: string;
};

type TenantBrand = {
  id: string;
  name: string;
  products: TenantProduct[];
};

type TenantClient = {
  id: string;
  name: string;
  brands: TenantBrand[];
};

type TenantState = {
  clientId: string;
  brandId: string | null;
  productId: string | null;
  clientName: string;
  brandName: string | null;
  productName: string | null;
  clients: TenantClient[];
  isAdminMode: boolean;
  setClientId: (clientId: string) => void;
  setBrandId: (brandId: string | null) => void;
  setProductId: (productId: string | null) => void;
};

const CLIENT_STORAGE_KEY = "client_id";
const BRAND_STORAGE_KEY = "brand_id";
const PRODUCT_STORAGE_KEY = "product_id";

const DEFAULT_CLIENTS: TenantClient[] = [
  {
    id: "client-samsung",
    name: "Samsung",
    brands: [
      {
        id: "brand-samsung",
        name: "Samsung",
        products: [{ id: "prod-qn90b", name: "QN90B QLED TV" }],
      },
    ],
  },
  {
    id: "client-under-armour",
    name: "Under Armour",
    brands: [
      {
        id: "brand-under-armour",
        name: "Under Armour",
        products: [{ id: "prod-ua-backpack", name: "UA Storm 40L Backpack" }],
      },
    ],
  },
  {
    id: "client-ikea",
    name: "IKEA",
    brands: [
      {
        id: "brand-ikea",
        name: "IKEA",
        products: [{ id: "prod-markus", name: "MARKUS Chair" }],
      },
    ],
  },
];

const TenantContext = createContext<TenantState | null>(null);

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const { user } = useUser();
  const userId = user?.id ?? null;
  const [clientId, setClientIdState] = useState(
    process.env.NEXT_PUBLIC_CLIENT_ID ?? DEFAULT_CLIENTS[0]?.id ?? "client-samsung",
  );
  const [brandId, setBrandIdState] = useState<string | null>(null);
  const [productId, setProductIdState] = useState<string | null>(null);
  const [clients, setClients] = useState<TenantClient[]>(DEFAULT_CLIENTS);
  const isAdminMode = process.env.NEXT_PUBLIC_ADMIN_MODE === "true";

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedClient = window.localStorage.getItem(CLIENT_STORAGE_KEY);
    const storedBrand = window.localStorage.getItem(BRAND_STORAGE_KEY);
    const storedProduct = window.localStorage.getItem(PRODUCT_STORAGE_KEY);
    const fallbackClient = clients[0]?.id ?? "client-samsung";
    const nextClient =
      storedClient && clients.some((client) => client.id === storedClient)
        ? storedClient
        : fallbackClient;
    setClientIdState(nextClient);
    if (storedBrand) setBrandIdState(storedBrand);
    if (storedProduct) setProductIdState(storedProduct);
    window.localStorage.setItem(CLIENT_STORAGE_KEY, nextClient);
  }, [clients]);

  useEffect(() => {
    if (!isAdminMode || !userId) return;
    let isActive = true;
    (async () => {
      try {
        const response = await listAdminClients(userId);
        const adminClients: TenantClient[] = (response.clients ?? []).map((client) => ({
          id: client.id,
          name: client.name,
          brands: [],
        }));
        if (!isActive || adminClients.length === 0) return;
        setClients(adminClients);
        if (!adminClients.find((client) => client.id === clientId)) {
          setClientIdState(adminClients[0].id);
        }
      } catch (error) {
        // Falls back to DEFAULT_CLIENTS when admin mode isn't authorized (403) or backend is unreachable.
        console.warn("Admin client list unavailable; using default tenant list.", error);
      }
    })();
    return () => {
      isActive = false;
    };
  }, [clientId, isAdminMode, userId]);

  useEffect(() => {
    if (!isAdminMode || !userId || !clientId) return;
    let isActive = true;
    (async () => {
      const response = await listAdminBrands(clientId, userId);
      const brands = response.brands ?? [];
      const hydrated = await Promise.all(
        brands.map(async (brand) => {
          const productResponse = await listAdminProducts(brand.id, userId);
          const products = (productResponse.products ?? []).map((product) => ({
            id: product.id,
            name: product.name,
          }));
          return {
            id: brand.id,
            name: brand.name,
            products,
          };
        }),
      );
      if (!isActive) return;
      setClients((current) =>
        current.map((client) =>
          client.id === clientId ? { ...client, brands: hydrated } : client,
        ),
      );
      if (!hydrated.find((brand) => brand.id === brandId)) {
        setBrandIdState(hydrated[0]?.id ?? null);
        setProductIdState(null);
      }
    })();
    return () => {
      isActive = false;
    };
  }, [brandId, clientId, isAdminMode, userId]);

  const setClientId = useCallback((nextClientId: string) => {
    setClientIdState(nextClientId);
    setBrandIdState(null);
    setProductIdState(null);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(CLIENT_STORAGE_KEY, nextClientId);
      window.localStorage.removeItem(BRAND_STORAGE_KEY);
      window.localStorage.removeItem(PRODUCT_STORAGE_KEY);
    }
  }, []);

  const setBrandId = useCallback((nextBrandId: string | null) => {
    setBrandIdState(nextBrandId);
    setProductIdState(null);
    if (typeof window !== "undefined") {
      if (nextBrandId) {
        window.localStorage.setItem(BRAND_STORAGE_KEY, nextBrandId);
      } else {
        window.localStorage.removeItem(BRAND_STORAGE_KEY);
      }
      window.localStorage.removeItem(PRODUCT_STORAGE_KEY);
    }
  }, []);

  const setProductId = useCallback((nextProductId: string | null) => {
    setProductIdState(nextProductId);
    if (typeof window !== "undefined") {
      if (nextProductId) {
        window.localStorage.setItem(PRODUCT_STORAGE_KEY, nextProductId);
      } else {
        window.localStorage.removeItem(PRODUCT_STORAGE_KEY);
      }
    }
  }, []);

  const selectedClient = clients.find((client) => client.id === clientId);
  const selectedBrand = selectedClient?.brands.find((brand) => brand.id === brandId) ?? null;
  const selectedProduct =
    selectedBrand?.products.find((product) => product.id === productId) ?? null;

  useEffect(() => {
    if (!selectedBrand) return;
    if (productId && !selectedProduct) {
      setProductId(null);
    }
  }, [productId, selectedBrand, selectedProduct, setProductId]);

  const value = useMemo<TenantState>(
    () => ({
      clientId,
      brandId,
      productId,
      clientName: selectedClient?.name ?? clientId,
      brandName: selectedBrand?.name ?? null,
      productName: selectedProduct?.name ?? null,
      clients,
      isAdminMode,
      setClientId,
      setBrandId,
      setProductId,
    }),
    [
      clientId,
      brandId,
      productId,
      selectedClient?.name,
      selectedBrand?.name,
      selectedProduct?.name,
      clients,
      isAdminMode,
      setClientId,
      setBrandId,
      setProductId,
    ],
  );

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}

export function useTenant() {
  const ctx = useContext(TenantContext);
  if (!ctx) {
    throw new Error("useTenant must be used within TenantProvider");
  }
  return ctx;
}
