"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import type {
  AdminBrand,
  AdminClient,
  AdminClientUser,
  AdminProduct,
  AdminPlatformProfile,
  AdminSkill,
  AdminLLMConfigResponse,
  LoopMaintenanceRunHistoryItem,
  LoopMaintenanceRunResponse,
  SessionSummary,
} from "../../lib/types";
import {
  addAdminClientUser,
  autofillAdminProductCanonicalSpec,
  createAdminBrand,
  createAdminClient,
  createAdminProduct,
  deleteConversationSession,
  getAdminSkill,
  getAdminPlatformProfile,
  listAdminBrands,
  listAdminClientUsers,
  listAdminClients,
  listAdminProducts,
  listAdminSkillHistory,
  listConversationSessions,
  updateAdminSkill,
  updateAdminProduct,
  updateAdminPlatformProfile,
  getAdminLlmConfig,
  updateAdminLlmConfig,
  activateAdminLlmProvider,
  listAdminLoopMaintenanceRuns,
  runAdminLoopMaintenance,
} from "../../lib/api";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { useTenant } from "../../components/tenant/TenantProvider";

const emptyForm = {
  id: "",
  name: "",
  description: "",
  productUrl: "",
  role: "analyst",
  memberUserId: "",
};

const canonicalOntology: Record<
  string,
  {
    label: string;
    subCategories: string[];
    useCases: string[];
    archetypes: string[];
    featureConcepts: string[];
    constraints: string[];
    exclusions: string[];
  }
> = {
  running_shoes: {
    label: "Running shoes",
    subCategories: ["daily_trainer", "race_day", "stability", "trail"],
    useCases: ["daily_training", "long_distance", "speed_work", "injury_prevention"],
    archetypes: ["beginner_runner", "performance_runner", "injury_conscious_runner"],
    featureConcepts: ["lightweight", "cushioning", "stability", "breathability"],
    constraints: ["budget_sensitive", "availability_required", "fast_delivery"],
    exclusions: ["elite_racer_only", "hiking_use", "indoor_only"],
  },
  television: {
    label: "Television",
    subCategories: ["living_room", "gaming_tv", "bright_room", "budget_tv"],
    useCases: ["movie_night", "sports_viewing", "gaming", "bright_room_viewing"],
    archetypes: ["value_seeker", "quality_seeker", "gamer"],
    featureConcepts: ["brightness", "anti_reflective", "motion_clarity", "size_fit"],
    constraints: ["budget_sensitive", "availability_required", "screen_size_required"],
    exclusions: ["projector_only", "audio_only", "outdoor_only"],
  },
  sports_apparel: {
    label: "Sports apparel",
    subCategories: ["running_vest", "training_top", "weather_layer"],
    useCases: ["road_running", "winter_training", "outdoor_sessions"],
    archetypes: ["daily_athlete", "commuter_runner", "endurance_runner"],
    featureConcepts: ["weather_protection", "breathability", "comfort_fit", "storage"],
    constraints: ["budget_sensitive", "weather_specific", "availability_required"],
    exclusions: ["formalwear_only", "kids_only", "non_sport_use"],
  },
};

const LLM_PROVIDERS = [
  { id: "openrouter", label: "OpenRouter" },
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Claude (Anthropic)" },
  { id: "gemini", label: "Gemini" },
] as const;

const LLM_MODEL_OPTIONS: Record<string, string[]> = {
  openrouter: ["openai/gpt-oss-120b"],
  openai: ["gpt-5.2-2025-12-11"],
  anthropic: ["claude-sonnet-4-5-20250929"],
  gemini: ["gemini-3-flash-preview"],
};

export default function AdminPage() {
  const router = useRouter();
  const { user } = useUser();
  const {
    clientId: tenantClientId,
    brandId: tenantBrandId,
    productId: tenantProductId,
    setClientId: setTenantClientId,
    setBrandId: setTenantBrandId,
    setProductId: setTenantProductId,
  } = useTenant();
  const userId = user?.id ?? null;
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isHistoryOpen, setHistoryOpen] = useState(false);
  const [isHistoryClosing, setHistoryClosing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const [clients, setClients] = useState<AdminClient[]>([]);
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [clientUsers, setClientUsers] = useState<AdminClientUser[]>([]);
  const [platformProfile, setPlatformProfile] = useState<AdminPlatformProfile | null>(null);
  const [platformProfileText, setPlatformProfileText] = useState<string>("");
  const [platformProfileName, setPlatformProfileName] = useState<string>("");
  const [platformProfileVersion, setPlatformProfileVersion] = useState<string>("2026-01-11");
  const [platformProfileError, setPlatformProfileError] = useState<string | null>(null);
  const [platformProfileSaved, setPlatformProfileSaved] = useState<boolean>(false);

  const [activeClientId, setActiveClientId] = useState<string>("");
  const [activeBrandId, setActiveBrandId] = useState<string>("");
  const [activeProductId, setActiveProductId] = useState<string>("");
  const [isIntentDrawerOpen, setIntentDrawerOpen] = useState(false);
  const [intentSpecSaved, setIntentSpecSaved] = useState(false);
  const [intentSpecError, setIntentSpecError] = useState<string | null>(null);
  const [intentSpecAutofillStatus, setIntentSpecAutofillStatus] = useState<string | null>(
    null,
  );
  const [intentSpecForm, setIntentSpecForm] = useState({
    category: "",
    subCategory: "",
    useCases: "",
    archetypes: "",
    featureConcepts: "",
    constraints: "",
    exclusions: "",
    objectiveKeywords: "",
    bannedKeywords: "",
  });

  const parseCsv = useCallback((value: string) => {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }, []);

  const slugify = useCallback((value: string) => {
    return value
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }, []);

  const skillNames = useMemo(() => ["signal_extractor", "copy_generator"], []);
  const [activeSkillName, setActiveSkillName] = useState<string>("signal_extractor");
  const [activeSkill, setActiveSkill] = useState<AdminSkill | null>(null);
  const [skillDescription, setSkillDescription] = useState<string>("");
  const [skillVersion, setSkillVersion] = useState<string>("");
  const [skillContent, setSkillContent] = useState<string>("");
  const [skillEnabled, setSkillEnabled] = useState<boolean>(true);
  const [skillError, setSkillError] = useState<string | null>(null);
  const [skillSaved, setSkillSaved] = useState<boolean>(false);
  const [skillHistory, setSkillHistory] = useState<
    { id: number; version?: string; changed_at?: string }[]
  >([]);

  const [llmConfig, setLlmConfig] = useState<AdminLLMConfigResponse | null>(null);
  const [llmConfigError, setLlmConfigError] = useState<string | null>(null);
  const [loopMaintenanceRunning, setLoopMaintenanceRunning] = useState(false);
  const [loopMaintenanceError, setLoopMaintenanceError] = useState<string | null>(null);
  const [loopMaintenanceResult, setLoopMaintenanceResult] =
    useState<LoopMaintenanceRunResponse | null>(null);
  const [loopMaintenanceHistory, setLoopMaintenanceHistory] = useState<
    LoopMaintenanceRunHistoryItem[]
  >([]);
  const [loopMaintenanceLookbackDays, setLoopMaintenanceLookbackDays] = useState("30");
  const [loopMaintenanceMinConfidence, setLoopMaintenanceMinConfidence] = useState("0.7");
  const [llmInputs, setLlmInputs] = useState<
    Record<
      string,
      {
        apiKey: string;
        validationApiKey: string;
        model: string;
        validationModel: string;
      }
    >
  >({});

  const [brandForm, setBrandForm] = useState({ ...emptyForm });
  const [productForm, setProductForm] = useState({ ...emptyForm });
  const [userForm, setUserForm] = useState({ ...emptyForm });
  const [showCreateBrand, setShowCreateBrand] = useState(false);
  const [showCreateProduct, setShowCreateProduct] = useState(false);
  const [isCreateClientDrawerOpen, setCreateClientDrawerOpen] = useState(false);
  const [createClientBusy, setCreateClientBusy] = useState(false);
  const [createClientError, setCreateClientError] = useState<string | null>(null);
  const [createClientSuccess, setCreateClientSuccess] = useState<string | null>(null);
  const [newClientForm, setNewClientForm] = useState({
    clientId: "",
    clientName: "",
    brandId: "",
    brandName: "",
    productsText: "",
    category: "",
    subCategory: "",
    useCases: "",
    archetypes: "",
    featureConcepts: "",
    constraints: "",
    exclusions: "",
    objectiveKeywords: "",
    bannedKeywords: "",
    ucpOfferUrl: "",
    ucpMerchantName: "",
    ucpCurrency: "GBP",
    acpEnableSearch: true,
    acpEnableCheckout: true,
  });

  useEffect(() => {
    if (!userId) return;
    void listAdminClients(userId).then((response) => {
      const items = response.clients ?? [];
      setClients(items);
      if (items.length === 0) {
        setActiveClientId("");
      } else if (tenantClientId && items.some((item) => item.id === tenantClientId)) {
        setActiveClientId(tenantClientId);
      } else if (!activeClientId && items[0]?.id) {
        setActiveClientId(items[0].id);
      }
    });
  }, [activeClientId, tenantClientId, userId]);

  useEffect(() => {
    if (!userId) return;
    void getAdminPlatformProfile(userId).then((response) => {
      if (!response.profile) return;
      setPlatformProfile(response.profile);
      setPlatformProfileText(
        JSON.stringify(response.profile.profile ?? {}, null, 2),
      );
      setPlatformProfileName(response.profile.name ?? "UCP Platform Profile");
      setPlatformProfileVersion(response.profile.version ?? "2026-01-11");
    });
  }, [userId]);

  useEffect(() => {
    if (!userId || !activeSkillName) return;
    void getAdminSkill(activeSkillName, userId).then((response) => {
      if (!response.skill) return;
      setActiveSkill(response.skill);
      setSkillDescription(response.skill.description ?? "");
      setSkillVersion(response.skill.version ?? "");
      setSkillContent(response.skill.content ?? "");
      setSkillEnabled(response.skill.enabled ?? true);
    });
    void listAdminSkillHistory(activeSkillName, userId, 5).then((response) => {
      setSkillHistory(response.history ?? []);
    });
  }, [activeSkillName, userId]);

  useEffect(() => {
    if (!userId) return;
    void getAdminLlmConfig(userId)
      .then((response) => {
        setLlmConfig(response);
        setLlmConfigError(null);
        setLlmInputs((current) => {
          const next = { ...current };
          LLM_PROVIDERS.forEach((provider) => {
            const summary = response.providers?.[provider.id] ?? {};
            next[provider.id] = {
              apiKey: "",
              validationApiKey: "",
              model:
                summary.model ||
                LLM_MODEL_OPTIONS[provider.id]?.[0] ||
                "",
              validationModel:
                summary.validation_model ||
                LLM_MODEL_OPTIONS[provider.id]?.[0] ||
                "",
            };
          });
          return next;
        });
      })
      .catch((err) => {
        setLlmConfig(null);
        setLlmConfigError(err instanceof Error ? err.message : "Unable to load");
      });
  }, [userId]);

  useEffect(() => {
    if (!activeClientId || !userId) {
      setBrands([]);
      setProducts([]);
      setClientUsers([]);
      return;
    }
    void listAdminBrands(activeClientId, userId).then((response) => {
      const items = response.brands ?? [];
      setBrands(items);
      if (items.length === 0) {
        setActiveBrandId("");
      } else if (tenantBrandId && items.some((item) => item.id === tenantBrandId)) {
        setActiveBrandId(tenantBrandId);
      } else if (!activeBrandId && items[0]?.id) {
        setActiveBrandId(items[0].id);
      }
    });
    void listAdminClientUsers(activeClientId, userId).then((response) => {
      setClientUsers(response.users ?? []);
    });
  }, [activeBrandId, activeClientId, tenantBrandId, userId]);

  useEffect(() => {
    if (!activeBrandId || !userId) {
      setProducts([]);
      return;
    }
    void listAdminProducts(activeBrandId, userId).then((response) => {
      setProducts(response.products ?? []);
    });
  }, [activeBrandId, userId]);

  useEffect(() => {
    if (!products.length) {
      setActiveProductId("");
      return;
    }
    if (
      tenantProductId &&
      products.some((product) => product.id === tenantProductId) &&
      activeProductId !== tenantProductId
    ) {
      setActiveProductId(tenantProductId);
      return;
    }
    if (!products.some((product) => product.id === activeProductId)) {
      setActiveProductId(products[0].id);
    }
  }, [activeProductId, products, tenantProductId]);

  useEffect(() => {
    if (!tenantClientId || clients.length === 0) return;
    if (
      clients.some((client) => client.id === tenantClientId) &&
      activeClientId !== tenantClientId
    ) {
      setActiveClientId(tenantClientId);
    }
  }, [activeClientId, clients, tenantClientId]);

  useEffect(() => {
    if (!tenantBrandId || brands.length === 0) return;
    if (
      brands.some((brand) => brand.id === tenantBrandId) &&
      activeBrandId !== tenantBrandId
    ) {
      setActiveBrandId(tenantBrandId);
    }
  }, [activeBrandId, brands, tenantBrandId]);

  useEffect(() => {
    const product = products.find((item) => item.id === activeProductId);
    const spec =
      ((product?.metadata?.canonical_intent_spec as Record<string, unknown>) ?? {});
    const listToText = (value: unknown) =>
      Array.isArray(value) ? value.join(", ") : "";
    setIntentSpecForm({
      category: String(spec.category ?? ""),
      subCategory: String(spec.sub_category ?? ""),
      useCases: listToText(spec.use_cases),
      archetypes: listToText(spec.audience_archetypes),
      featureConcepts: listToText(spec.feature_concepts),
      constraints: listToText(spec.core_constraints),
      exclusions: listToText(spec.must_not_target),
      objectiveKeywords: listToText(spec.objective_keywords),
      bannedKeywords: listToText(spec.banned_keywords),
    });
  }, [activeProductId, products]);

  useEffect(() => {
    if (!userId) return;
    void listConversationSessions(userId).then((response) => {
      setSessions(response.sessions ?? []);
    });
  }, [userId]);

  const selectedClient = useMemo(
    () => clients.find((client) => client.id === activeClientId),
    [clients, activeClientId],
  );

  const selectedBrand = useMemo(
    () => brands.find((brand) => brand.id === activeBrandId),
    [brands, activeBrandId],
  );

  const selectedProduct = useMemo(
    () => products.find((product) => product.id === activeProductId),
    [products, activeProductId],
  );

  const onboardingCompletion = useMemo(() => {
    const spec =
      ((selectedProduct?.metadata?.canonical_intent_spec as Record<string, unknown>) ??
        {});
    const doneClient = Boolean(activeClientId);
    const doneBrand = Boolean(activeBrandId);
    const doneProduct = Boolean(activeProductId);
    const doneIntent =
      Boolean(spec.category) &&
      Array.isArray(spec.use_cases) &&
      spec.use_cases.length > 0;
    const completed = [doneClient, doneBrand, doneProduct, doneIntent].filter(Boolean)
      .length;
    return {
      completed,
      total: 4,
      doneClient,
      doneBrand,
      doneProduct,
      doneIntent,
    };
  }, [activeBrandId, activeClientId, activeProductId, selectedProduct]);

  const selectedOntology = useMemo(() => {
    const key = intentSpecForm.category;
    return key ? canonicalOntology[key] : null;
  }, [intentSpecForm.category]);

  const canCreateBrand = Boolean(
    userId && activeClientId && brandForm.id.trim() && brandForm.name.trim(),
  );
  const canCreateProduct = Boolean(
    userId &&
      activeBrandId &&
      productForm.id.trim() &&
      productForm.name.trim() &&
      productForm.description.trim(),
  );
  const canSaveIntentSpec = Boolean(
    selectedProduct &&
      intentSpecForm.category.trim() &&
      parseCsv(intentSpecForm.useCases).length > 0,
  );

  const onboardingOntology = useMemo(() => {
    const key = newClientForm.category;
    return key ? canonicalOntology[key] : null;
  }, [newClientForm.category]);

  const onboardingUseCases = useMemo(() => {
    const selected = parseCsv(newClientForm.useCases);
    const base = onboardingOntology?.useCases ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [newClientForm.useCases, parseCsv, onboardingOntology]);

  const onboardingArchetypes = useMemo(() => {
    const selected = parseCsv(newClientForm.archetypes);
    const base = onboardingOntology?.archetypes ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [newClientForm.archetypes, parseCsv, onboardingOntology]);

  const onboardingFeatures = useMemo(() => {
    const selected = parseCsv(newClientForm.featureConcepts);
    const base = onboardingOntology?.featureConcepts ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [newClientForm.featureConcepts, parseCsv, onboardingOntology]);

  const onboardingConstraints = useMemo(() => {
    const selected = parseCsv(newClientForm.constraints);
    const base = onboardingOntology?.constraints ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [newClientForm.constraints, parseCsv, onboardingOntology]);

  const onboardingExclusions = useMemo(() => {
    const selected = parseCsv(newClientForm.exclusions);
    const base = onboardingOntology?.exclusions ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [newClientForm.exclusions, parseCsv, onboardingOntology]);

  const canSubmitNewClient = Boolean(
    userId &&
      newClientForm.clientId.trim() &&
      newClientForm.clientName.trim() &&
      newClientForm.brandId.trim() &&
      newClientForm.brandName.trim() &&
      newClientForm.category.trim() &&
      parseCsv(newClientForm.useCases).length > 0 &&
      newClientForm.productsText.trim(),
  );

  const ontologyUseCases = useMemo(() => {
    const selected = parseCsv(intentSpecForm.useCases);
    const base = selectedOntology?.useCases ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [intentSpecForm.useCases, parseCsv, selectedOntology]);

  const ontologyArchetypes = useMemo(() => {
    const selected = parseCsv(intentSpecForm.archetypes);
    const base = selectedOntology?.archetypes ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [intentSpecForm.archetypes, parseCsv, selectedOntology]);

  const ontologyFeatureConcepts = useMemo(() => {
    const selected = parseCsv(intentSpecForm.featureConcepts);
    const base = selectedOntology?.featureConcepts ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [intentSpecForm.featureConcepts, parseCsv, selectedOntology]);

  const ontologyConstraints = useMemo(() => {
    const selected = parseCsv(intentSpecForm.constraints);
    const base = selectedOntology?.constraints ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [intentSpecForm.constraints, parseCsv, selectedOntology]);

  const ontologyExclusions = useMemo(() => {
    const selected = parseCsv(intentSpecForm.exclusions);
    const base = selectedOntology?.exclusions ?? [];
    return Array.from(new Set([...base, ...selected]));
  }, [intentSpecForm.exclusions, parseCsv, selectedOntology]);

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

  const handleBulkDeleteSessions = useCallback(
    async (sessionIds: string[]) => {
      if (!sessionIds.length || !userId) return;
      const ok = window.confirm(
        `Delete ${sessionIds.length} chat session${sessionIds.length === 1 ? "" : "s"}?`,
      );
      if (!ok) return;
      await Promise.all(
        sessionIds.map((id) =>
          deleteConversationSession(id, userId).catch(() => null),
        ),
      );
      setSessions((current) => current.filter((item) => !sessionIds.includes(item.id)));
      setDeleteTargetId(null);
    },
    [userId],
  );

  const handleCreateClientOnboarding = useCallback(async () => {
    if (!userId || !canSubmitNewClient) return;
    setCreateClientBusy(true);
    setCreateClientError(null);
    setCreateClientSuccess(null);
    try {
      const client = await createAdminClient(
        {
          id: newClientForm.clientId.trim(),
          name: newClientForm.clientName.trim(),
        },
        userId,
      );
      const brand = await createAdminBrand(
        client.client.id,
        {
          id: newClientForm.brandId.trim(),
          name: newClientForm.brandName.trim(),
        },
        userId,
      );

      const canonicalSpec = {
        category: newClientForm.category.trim(),
        sub_category: newClientForm.subCategory.trim() || null,
        use_cases: parseCsv(newClientForm.useCases),
        audience_archetypes: parseCsv(newClientForm.archetypes),
        feature_concepts: parseCsv(newClientForm.featureConcepts),
        core_constraints: parseCsv(newClientForm.constraints),
        must_not_target: parseCsv(newClientForm.exclusions),
        objective_keywords: parseCsv(newClientForm.objectiveKeywords),
        banned_keywords: parseCsv(newClientForm.bannedKeywords),
        source: ["admin_onboarding"],
        updated_at: new Date().toISOString(),
      };

      const productLines = newClientForm.productsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      if (productLines.length === 0) {
        throw new Error("Add at least one product line.");
      }

      let firstProductId: string | null = null;
      for (const line of productLines) {
        const parts = line.split("|").map((item) => item.trim());
        if (parts.length < 2) {
          throw new Error(
            "Each product line must be: product-id|product name|short description",
          );
        }
        const hasExplicitId = parts.length >= 3;
        const productId = hasExplicitId
          ? parts[0]
          : `product-${slugify(parts[0])}`;
        const productName = hasExplicitId ? parts[1] : parts[0];
        const productDescription = hasExplicitId ? parts[2] : parts[1];
        if (!productId || !productName || !productDescription) {
          throw new Error(
            "Each product line must include product id/name/description.",
          );
        }
        const productResponse = await createAdminProduct(
          brand.brand.id,
          {
            id: productId,
            name: productName,
            description: productDescription,
            metadata: {
              canonical_intent_spec: canonicalSpec,
              ucp: {
                offer_url: newClientForm.ucpOfferUrl.trim() || undefined,
                merchant_name: newClientForm.ucpMerchantName.trim() || undefined,
                currency: newClientForm.ucpCurrency.trim() || "GBP",
                category: canonicalSpec.category,
                sub_category: canonicalSpec.sub_category,
                use_cases: canonicalSpec.use_cases,
                audience_archetypes: canonicalSpec.audience_archetypes,
                feature_concepts: canonicalSpec.feature_concepts,
                constraints: canonicalSpec.core_constraints,
              },
              acp: {
                enable_search: newClientForm.acpEnableSearch,
                enable_checkout: newClientForm.acpEnableCheckout,
                category: canonicalSpec.category,
                sub_category: canonicalSpec.sub_category,
                use_cases: canonicalSpec.use_cases,
                audience_archetypes: canonicalSpec.audience_archetypes,
                feature_concepts: canonicalSpec.feature_concepts,
                constraints: canonicalSpec.core_constraints,
              },
            },
          },
          userId,
        );
        if (!firstProductId) firstProductId = productResponse.product.id;
      }

      const nextClientId = client.client.id;
      const nextBrandId = brand.brand.id;
      const nextProductId = firstProductId;

      setClients((current) => [...current, client.client]);
      setActiveClientId(nextClientId);
      setTenantClientId(nextClientId);
      setBrands([brand.brand]);
      setActiveBrandId(nextBrandId);
      setTenantBrandId(nextBrandId);
      if (nextProductId) {
        setActiveProductId(nextProductId);
        setTenantProductId(nextProductId);
      }

      setCreateClientSuccess(
        `Created client ${client.client.name} with brand ${brand.brand.name} and ${productLines.length} product(s).`,
      );
      setNewClientForm({
        clientId: "",
        clientName: "",
        brandId: "",
        brandName: "",
        productsText: "",
        category: "",
        subCategory: "",
        useCases: "",
        archetypes: "",
        featureConcepts: "",
        constraints: "",
        exclusions: "",
        objectiveKeywords: "",
        bannedKeywords: "",
        ucpOfferUrl: "",
        ucpMerchantName: "",
        ucpCurrency: "GBP",
        acpEnableSearch: true,
        acpEnableCheckout: true,
      });
      window.setTimeout(() => {
        setCreateClientSuccess(null);
        setCreateClientDrawerOpen(false);
      }, 1600);
    } catch (error) {
      setCreateClientError(
        error instanceof Error ? error.message : "Failed to onboard client.",
      );
    } finally {
      setCreateClientBusy(false);
    }
  }, [
    canSubmitNewClient,
    newClientForm,
    parseCsv,
    setTenantBrandId,
    setTenantClientId,
    setTenantProductId,
    slugify,
    userId,
  ]);

  const handleCreateBrand = useCallback(async () => {
    if (!userId || !activeClientId || !brandForm.id.trim() || !brandForm.name.trim())
      return;
    const response = await createAdminBrand(
      activeClientId,
      { id: brandForm.id.trim(), name: brandForm.name.trim() },
      userId,
    );
    setBrands((current) => [...current, response.brand]);
    setActiveBrandId(response.brand.id);
    setTenantBrandId(response.brand.id);
    setBrandForm({ ...emptyForm });
  }, [activeClientId, brandForm, setTenantBrandId, userId]);

  const handleCreateProduct = useCallback(async () => {
    if (!userId || !activeBrandId || !productForm.id.trim() || !productForm.name.trim())
      return;
    const metadata: Record<string, unknown> = {};
    if (productForm.productUrl?.trim()) {
      metadata.product_url = productForm.productUrl.trim();
    }
    const response = await createAdminProduct(
      activeBrandId,
      {
        id: productForm.id.trim(),
        name: productForm.name.trim(),
        description: productForm.description?.trim() || undefined,
        metadata: Object.keys(metadata).length ? metadata : undefined,
      },
      userId,
    );
    setProducts((current) => [...current, response.product]);
    setActiveProductId(response.product.id);
    setTenantProductId(response.product.id);
    setProductForm({ ...emptyForm });
  }, [activeBrandId, productForm, setTenantProductId, userId]);

  const handleSaveIntentSpec = useCallback(async () => {
    if (!userId || !activeBrandId || !selectedProduct) return;
    const currentMetadata = (selectedProduct.metadata ?? {}) as Record<string, unknown>;
    const canonicalSpec = {
      category: intentSpecForm.category.trim(),
      sub_category: intentSpecForm.subCategory.trim() || null,
      use_cases: parseCsv(intentSpecForm.useCases),
      audience_archetypes: parseCsv(intentSpecForm.archetypes),
      feature_concepts: parseCsv(intentSpecForm.featureConcepts),
      core_constraints: parseCsv(intentSpecForm.constraints),
      must_not_target: parseCsv(intentSpecForm.exclusions),
      objective_keywords: parseCsv(intentSpecForm.objectiveKeywords),
      banned_keywords: parseCsv(intentSpecForm.bannedKeywords),
      source: ["admin_onboarding"],
      updated_at: new Date().toISOString(),
    };
    try {
      const response = await updateAdminProduct(
        activeBrandId,
        selectedProduct.id,
        {
          metadata: {
            ...currentMetadata,
            canonical_intent_spec: canonicalSpec,
          },
        },
        userId,
      );
      if (response.product) {
        setProducts((current) =>
          current.map((product) =>
            product.id === response.product?.id ? response.product : product,
          ),
        );
      }
      setIntentSpecError(null);
      setIntentSpecSaved(true);
      window.setTimeout(() => setIntentSpecSaved(false), 1800);
    } catch (error) {
      setIntentSpecError("Failed to save canonical intent spec.");
    }
  }, [activeBrandId, intentSpecForm, parseCsv, selectedProduct, userId]);

  const handleAutofillIntentSpec = useCallback(
    async (mode: "preview" | "apply") => {
      if (!userId || !activeBrandId || !selectedProduct) return;
      try {
        const response = await autofillAdminProductCanonicalSpec(
          activeBrandId,
          selectedProduct.id,
          { mode },
          userId,
        );
        const spec = (response.result?.canonical_spec ?? {}) as Record<string, unknown>;
        const listToText = (value: unknown) =>
          Array.isArray(value) ? value.join(", ") : "";
        setIntentSpecForm({
          category: String(spec.category ?? ""),
          subCategory: String(spec.sub_category ?? ""),
          useCases: listToText(spec.use_cases),
          archetypes: listToText(spec.audience_archetypes),
          featureConcepts: listToText(spec.feature_concepts),
          constraints: listToText(spec.core_constraints),
          exclusions: listToText(spec.must_not_target),
          objectiveKeywords: listToText(spec.objective_keywords),
          bannedKeywords: listToText(spec.banned_keywords),
        });
        if (mode === "apply" && response.result?.product) {
          setProducts((current) =>
            current.map((product) =>
              product.id === response.result.product?.id ? response.result.product : product,
            ),
          );
          setIntentSpecSaved(true);
          window.setTimeout(() => setIntentSpecSaved(false), 1800);
        }
        const prompt = spec.clarification_prompt;
        if (typeof prompt === "string" && prompt.trim()) {
          setIntentSpecAutofillStatus(prompt);
        } else {
          setIntentSpecAutofillStatus(
            mode === "apply"
              ? "Canonical spec autofilled and saved from UCP/ACP/feed sources."
              : "Canonical spec preview loaded from UCP/ACP/feed sources.",
          );
        }
        setIntentSpecError(null);
      } catch (error) {
        setIntentSpecAutofillStatus(null);
        setIntentSpecError("Failed to autofill canonical intent spec.");
      }
    },
    [activeBrandId, selectedProduct, userId],
  );

  const handleAddClientUser = useCallback(async () => {
    if (!userId || !activeClientId || !userForm.memberUserId.trim()) return;
    const response = await addAdminClientUser(
      activeClientId,
      {
        member_user_id: userForm.memberUserId.trim(),
        role: userForm.role?.trim() || undefined,
      },
      userId,
    );
    setClientUsers((current) => [response.user, ...current]);
    setUserForm({ ...emptyForm });
  }, [activeClientId, userForm, userId]);

  const handleSavePlatformProfile = useCallback(async () => {
    if (!userId || !platformProfile) return;
    try {
      const parsed = JSON.parse(platformProfileText || "{}");
      const response = await updateAdminPlatformProfile(
        {
          name: platformProfileName || "UCP Platform Profile",
          version: platformProfileVersion || "2026-01-11",
          profile: parsed,
        },
        userId,
      );
      setPlatformProfile(response.profile);
      setPlatformProfileText(
        JSON.stringify(response.profile.profile ?? {}, null, 2),
      );
      setPlatformProfileName(response.profile.name ?? "UCP Platform Profile");
      setPlatformProfileVersion(response.profile.version ?? "2026-01-11");
      setPlatformProfileError(null);
      setPlatformProfileSaved(true);
      window.setTimeout(() => setPlatformProfileSaved(false), 1500);
    } catch (error) {
      setPlatformProfileError("Invalid JSON. Please fix the profile JSON.");
    }
  }, [platformProfile, platformProfileName, platformProfileText, platformProfileVersion, userId]);

  const handleSaveSkill = useCallback(async () => {
    if (!userId || !activeSkillName) return;
    if (!skillContent.trim()) {
      setSkillError("Skill content cannot be empty.");
      return;
    }
    try {
      const response = await updateAdminSkill(
        activeSkillName,
        {
          description: skillDescription || activeSkillName,
          version: skillVersion || "2026-02-01",
          content: skillContent,
          enabled: skillEnabled,
        },
        userId,
      );
      setActiveSkill(response.skill ?? null);
      setSkillError(null);
      setSkillSaved(true);
      void listAdminSkillHistory(activeSkillName, userId, 5).then((next) => {
        setSkillHistory(next.history ?? []);
      });
      window.setTimeout(() => setSkillSaved(false), 1500);
    } catch (error) {
      setSkillError("Failed to save skill.");
    }
  }, [activeSkillName, skillContent, skillDescription, skillEnabled, skillVersion, userId]);

  const handleLlmInputChange = useCallback(
    (
      provider: string,
      field: "apiKey" | "validationApiKey" | "model" | "validationModel",
      value: string,
    ) => {
      setLlmInputs((current) => ({
        ...current,
        [provider]: {
          apiKey: current[provider]?.apiKey ?? "",
          validationApiKey: current[provider]?.validationApiKey ?? "",
          model: current[provider]?.model ?? "",
          validationModel: current[provider]?.validationModel ?? "",
          [field]: value,
        },
      }));
    },
    [],
  );

  const handleSaveLlmProvider = useCallback(
    async (provider: string) => {
      if (!userId) return;
      const input = llmInputs[provider];
      if (!input) return;
      const payload: {
        user_id: string;
        api_key?: string;
        validation_api_key?: string;
        model?: string;
        validation_model?: string;
        activate?: boolean;
      } = {
        user_id: userId,
        model: input.model || undefined,
        validation_model: input.validationModel || undefined,
      };
      if (input.apiKey) payload.api_key = input.apiKey;
      if (input.validationApiKey) payload.validation_api_key = input.validationApiKey;
      try {
        const summary = await updateAdminLlmConfig(provider, payload);
        setLlmConfig(summary);
        setLlmConfigError(null);
        setLlmInputs((current) => ({
          ...current,
          [provider]: {
            ...current[provider],
            apiKey: "",
            validationApiKey: "",
          },
        }));
      } catch (error) {
        setLlmConfigError("Failed to save model configuration.");
      }
    },
    [llmInputs, userId],
  );

  const handleActivateLlmProvider = useCallback(
    async (provider: string) => {
      if (!userId) return;
      const input = llmInputs[provider];
      try {
        const summary = await activateAdminLlmProvider({
          user_id: userId,
          provider,
          model: input?.model || undefined,
        });
        setLlmConfig(summary);
        setLlmConfigError(null);
      } catch (error) {
        setLlmConfigError("Failed to activate provider.");
      }
    },
    [llmInputs, userId],
  );

  const handleRunLoopMaintenance = useCallback(async () => {
    if (!userId) return;
    setLoopMaintenanceRunning(true);
    try {
      const response = await runAdminLoopMaintenance(
        {
          client_id: activeClientId || undefined,
          lookback_days: Number(loopMaintenanceLookbackDays) || 30,
          min_confidence: Number(loopMaintenanceMinConfidence) || 0.7,
        },
        userId,
      );
      setLoopMaintenanceResult(response);
      setLoopMaintenanceHistory(response.history ?? []);
      setLoopMaintenanceError(null);
    } catch (error) {
      setLoopMaintenanceResult(null);
      setLoopMaintenanceError("Failed to run loop maintenance.");
    } finally {
      setLoopMaintenanceRunning(false);
    }
  }, [
    activeClientId,
    loopMaintenanceLookbackDays,
    loopMaintenanceMinConfidence,
    userId,
  ]);

  useEffect(() => {
    if (!userId || !activeClientId) {
      setLoopMaintenanceHistory([]);
      return;
    }
    void listAdminLoopMaintenanceRuns(
      {
        client_id: activeClientId,
        limit: 20,
      },
      userId,
    )
      .then((response) => {
        setLoopMaintenanceHistory(response.runs ?? []);
      })
      .catch(() => {
        setLoopMaintenanceHistory([]);
      });
  }, [activeClientId, userId]);

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
                className="button button--primary-subtle"
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
        onSelect={(session) => {
          router.push(`/?session=${session.id}`);
          handleCloseHistory();
        }}
        onRequestDelete={(sessionId) => setDeleteTargetId(sessionId)}
        onRequestDeleteSessionsBulk={handleBulkDeleteSessions}
      />
      <main className="main main--detail">
        <div className="detail admin">
          <DetailHeader title="Admin" onMenu={() => setSidebarOpen(true)} onBack={() => router.push("/")} />
          {!userId && (
            <div className="panel__card admin__panel">
              <h3>Sign in required</h3>
              <p className="panel__empty">
                Sign in with an admin account to manage clients, brands, and products.
              </p>
            </div>
          )}
          {userId && (
            <>
            <section className="panel__card admin-onboarding">
              <div className="panel__header">
                <h3>Client onboarding workspace</h3>
                <span className="panel__meta">
                  {onboardingCompletion.completed}/{onboardingCompletion.total} complete
                </span>
              </div>
              <div className="admin-onboarding__scope">
                <div className="admin__selector">
                  <label className="panel__label" htmlFor="admin-client-select">
                    Scope client
                  </label>
                  <select
                    id="admin-client-select"
                    value={activeClientId}
                    onChange={(event) => {
                      const nextClientId = event.target.value;
                      setActiveClientId(nextClientId);
                      setTenantClientId(nextClientId || "");
                      setActiveBrandId("");
                      setActiveProductId("");
                    }}
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
                    onChange={(event) => {
                      const nextBrandId = event.target.value;
                      setActiveBrandId(nextBrandId);
                      setTenantBrandId(nextBrandId || null);
                      setActiveProductId("");
                    }}
                    disabled={!activeClientId || brands.length === 0}
                  >
                    {brands.length === 0 ? (
                      <option value="">Select brand</option>
                    ) : null}
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
                    onChange={(event) => {
                      const nextProductId = event.target.value;
                      setActiveProductId(nextProductId);
                      setTenantProductId(nextProductId || null);
                    }}
                    disabled={!activeBrandId || products.length === 0}
                  >
                    {products.length === 0 ? (
                      <option value="">Select product</option>
                    ) : null}
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <p className="panel__meta">
                All onboarding changes are saved against the selected scope above.
              </p>
              <div className="panel__actions">
                <button
                  type="button"
                  className="button button--primary-subtle"
                  onClick={() => {
                    setCreateClientDrawerOpen(true);
                    setCreateClientError(null);
                    setCreateClientSuccess(null);
                  }}
                >
                  Add new client
                </button>
              </div>
              <div className="admin-onboarding__panels">
                <details>
                  <summary>Client access</summary>
                  {activeClientId ? (
                    <div className="admin__form">
                      <p className="panel__meta">
                        Users added here get access to:{" "}
                        <strong>{selectedClient?.name ?? activeClientId}</strong>
                      </p>
                      <span className="panel__label">Client users</span>
                      {clientUsers.length === 0 ? (
                        <p className="panel__empty">No users yet.</p>
                      ) : (
                        <ul className="admin__list">
                          {clientUsers.map((member) => (
                            <li key={member.id}>
                              <span>{member.user_id}</span>
                              <span className="admin__meta">
                                {member.role ?? "analyst"}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                      <input
                        type="text"
                        placeholder="Clerk user id"
                        value={userForm.memberUserId}
                        onChange={(event) =>
                          setUserForm((current) => ({
                            ...current,
                            memberUserId: event.target.value,
                          }))
                        }
                      />
                      <input
                        type="text"
                        placeholder="Role (analyst, admin)"
                        value={userForm.role}
                        onChange={(event) =>
                          setUserForm((current) => ({ ...current, role: event.target.value }))
                        }
                      />
                      <button
                        type="button"
                        className="button button--primary-subtle"
                        onClick={handleAddClientUser}
                        disabled={!userForm.memberUserId.trim()}
                      >
                        Add user to selected client
                      </button>
                    </div>
                  ) : (
                    <p className="panel__empty">Select a client first.</p>
                  )}
                </details>
                <details>
                  <summary>Brand setup</summary>
                  {activeClientId ? (
                    <>
                      <p className="panel__meta">
                        Creates and edits brands for client:{" "}
                        <strong>{selectedClient?.name ?? activeClientId}</strong>
                      </p>
                      {brands.length === 0 ? (
                        <p className="panel__empty">No brands yet.</p>
                      ) : (
                        <ul className="admin__list">
                          {brands.map((brand) => (
                            <li key={brand.id}>
                              <span>{brand.name}</span>
                              <span className="admin__meta">{brand.id}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                      <div className="panel__actions">
                        <button
                          type="button"
                          className="button button--ghost"
                          onClick={() => setShowCreateBrand((current) => !current)}
                        >
                          {showCreateBrand ? "Hide create brand form" : "Add new brand"}
                        </button>
                      </div>
                      {showCreateBrand ? (
                        <div className="admin__form">
                          <span className="panel__label">
                            Create brand for {selectedClient?.name ?? activeClientId}
                          </span>
                          <input
                            type="text"
                            placeholder="brand-id"
                            value={brandForm.id}
                            onChange={(event) =>
                              setBrandForm((current) => ({ ...current, id: event.target.value }))
                            }
                            required
                          />
                          <input
                            type="text"
                            placeholder="Brand name"
                            value={brandForm.name}
                            onChange={(event) =>
                              setBrandForm((current) => ({ ...current, name: event.target.value }))
                            }
                            required
                          />
                          <button
                            type="button"
                            className="button button--primary-subtle"
                            onClick={handleCreateBrand}
                            disabled={!canCreateBrand}
                          >
                            Add brand
                          </button>
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <p className="panel__empty">Select a client first.</p>
                  )}
                </details>
                <details>
                  <summary>Product catalog</summary>
                  {activeBrandId ? (
                    <>
                      <p className="panel__meta">
                        Creates and edits products for brand:{" "}
                        <strong>{selectedBrand?.name ?? activeBrandId}</strong>
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
                          onClick={() => setShowCreateProduct((current) => !current)}
                        >
                          {showCreateProduct
                            ? "Hide create product form"
                            : "Add new product"}
                        </button>
                      </div>
                      {showCreateProduct ? (
                        <div className="admin__form">
                          <span className="panel__label">
                            Create product for {selectedBrand?.name ?? activeBrandId}
                          </span>
                          <input
                            type="text"
                            placeholder="product-id"
                            value={productForm.id}
                            onChange={(event) =>
                              setProductForm((current) => ({ ...current, id: event.target.value }))
                            }
                            required
                          />
                          <input
                            type="text"
                            placeholder="Product name"
                            value={productForm.name}
                            onChange={(event) =>
                              setProductForm((current) => ({ ...current, name: event.target.value }))
                            }
                            required
                          />
                          <textarea
                            rows={2}
                            placeholder="Short description (required)"
                            value={productForm.description}
                            onChange={(event) =>
                              setProductForm((current) => ({
                                ...current,
                                description: event.target.value,
                              }))
                            }
                            required
                          />
                          <input
                            type="url"
                            placeholder="Product URL (optional)"
                            value={productForm.productUrl}
                            onChange={(event) =>
                              setProductForm((current) => ({
                                ...current,
                                productUrl: event.target.value,
                              }))
                            }
                          />
                          <button
                            type="button"
                            className="button button--primary-subtle"
                            onClick={handleCreateProduct}
                            disabled={!canCreateProduct}
                          >
                            Add product
                          </button>
                        </div>
                      ) : null}
                      <details>
                        <summary>Platform profile (UCP)</summary>
                        {!platformProfile ? (
                          <p className="panel__empty">Platform profile not loaded yet.</p>
                        ) : (
                          <div className="admin__form">
                            <span className="panel__label">Profile JSON</span>
                            <input
                              type="text"
                              placeholder="Profile name"
                              value={platformProfileName}
                              onChange={(event) => setPlatformProfileName(event.target.value)}
                            />
                            <input
                              type="text"
                              placeholder="Version"
                              value={platformProfileVersion}
                              onChange={(event) => setPlatformProfileVersion(event.target.value)}
                            />
                            <textarea
                              rows={8}
                              value={platformProfileText}
                              onChange={(event) => setPlatformProfileText(event.target.value)}
                            />
                            {platformProfileError && (
                              <p className="panel__error">{platformProfileError}</p>
                            )}
                            {platformProfileSaved && (
                              <p className="panel__success">Saved platform profile.</p>
                            )}
                            <button
                              type="button"
                              className="button button--primary-subtle"
                              onClick={handleSavePlatformProfile}
                            >
                              Save profile
                            </button>
                          </div>
                        )}
                      </details>
                    </>
                  ) : (
                    <p className="panel__empty">Select a brand first.</p>
                  )}
                </details>
                <details>
                  <summary>Canonical intent spec</summary>
                  <p className="panel__meta">
                    Capture objective product context used by bottom-up query generation.
                  </p>
                  <p className="panel__meta">
                    Saved under selected product metadata path:
                    {" "}
                    <code>canonical_intent_spec</code>.
                  </p>
                  <button
                    type="button"
                    className="button button--primary-subtle"
                    onClick={() => setIntentDrawerOpen(true)}
                    disabled={!selectedProduct}
                  >
                    Open intent spec editor
                  </button>
                  {intentSpecSaved ? (
                    <p className="panel__success">Saved canonical intent spec.</p>
                  ) : null}
                  {intentSpecAutofillStatus ? (
                    <p className="panel__meta">{intentSpecAutofillStatus}</p>
                  ) : null}
                  {intentSpecError ? (
                    <p className="panel__error">{intentSpecError}</p>
                  ) : null}
                </details>
                <details>
                  <summary>Review</summary>
                  <ul className="admin__list">
                    <li>
                      <span>Client</span>
                      <span className="admin__meta">{onboardingCompletion.doneClient ? "Done" : "Missing"}</span>
                    </li>
                    <li>
                      <span>Brand</span>
                      <span className="admin__meta">{onboardingCompletion.doneBrand ? "Done" : "Missing"}</span>
                    </li>
                    <li>
                      <span>Product</span>
                      <span className="admin__meta">{onboardingCompletion.doneProduct ? "Done" : "Missing"}</span>
                    </li>
                    <li>
                      <span>Canonical intent spec</span>
                      <span className="admin__meta">{onboardingCompletion.doneIntent ? "Done" : "Missing"}</span>
                    </li>
                  </ul>
                </details>
              </div>
            </section>

            <section className="panel__card admin-ops">
              <div className="panel__header">
                <h3>Operational controls</h3>
              </div>
              <details className="admin-ops__details">
                <summary>Model gateway</summary>
                {!userId ? (
                  <p className="panel__empty">Sign in to manage model keys.</p>
                ) : (
                  <div className="admin__form">
                    {llmConfigError ? (
                      <p className="panel__error">{llmConfigError}</p>
                    ) : null}
                    <div className="panel__chips">
                      {LLM_PROVIDERS.map((provider) => {
                        const summary = llmConfig?.providers?.[provider.id];
                        const status = summary?.configured ? "ready" : "missing";
                        return (
                          <span
                            key={provider.id}
                            className={`panel__chip ${
                              summary?.is_active ? "is-ready" : summary?.configured ? "is-ready" : "is-missing"
                            }`}
                          >
                            {provider.label}: {summary?.is_active ? "active" : status}
                          </span>
                        );
                      })}
                    </div>
                    {LLM_PROVIDERS.map((provider) => {
                      const summary = llmConfig?.providers?.[provider.id];
                      const input = llmInputs[provider.id] || {
                        apiKey: "",
                        validationApiKey: "",
                        model: summary?.model || LLM_MODEL_OPTIONS[provider.id]?.[0] || "",
                        validationModel:
                          summary?.validation_model ||
                          LLM_MODEL_OPTIONS[provider.id]?.[0] ||
                          "",
                      };
                      const baseOptions = LLM_MODEL_OPTIONS[provider.id] || [];
                      const modelOptions = input.model && !baseOptions.includes(input.model)
                        ? [input.model, ...baseOptions]
                        : baseOptions;
                      const validationOptions =
                        input.validationModel &&
                        !baseOptions.includes(input.validationModel)
                          ? [input.validationModel, ...baseOptions]
                          : baseOptions;
                      return (
                        <div key={provider.id} className="panel__card panel__card--compact">
                          <div className="panel__header">
                            <h4>{provider.label}</h4>
                            <span className="panel__meta">
                              Chat: {summary?.chat_configured ? "set" : "missing"} ·
                              Validation: {summary?.validation_configured ? "set" : "missing"}
                            </span>
                          </div>
                          <div className="panel__grid">
                            <label className="panel__label">
                              <span>Chat model</span>
                              <input
                                className="panel__input panel__input--neutral"
                                type="text"
                                spellCheck={false}
                                autoCorrect="off"
                                autoCapitalize="none"
                                value={input.model}
                                onChange={(event) =>
                                  handleLlmInputChange(
                                    provider.id,
                                    "model",
                                    event.target.value,
                                  )
                                }
                              />
                            </label>
                            <label className="panel__label">
                              <span>Validation model</span>
                              <input
                                className="panel__input panel__input--neutral"
                                type="text"
                                list={`admin-llm-validation-models-${provider.id}`}
                                spellCheck={false}
                                autoCorrect="off"
                                autoCapitalize="none"
                                value={input.validationModel}
                                onChange={(event) =>
                                  handleLlmInputChange(
                                    provider.id,
                                    "validationModel",
                                    event.target.value,
                                  )
                                }
                              />
                              <datalist
                                id={`admin-llm-validation-models-${provider.id}`}
                              >
                                {validationOptions.map((option) => (
                                  <option key={option} value={option} />
                                ))}
                              </datalist>
                            </label>
                            <label className="panel__label">
                              <span>Chat key (BYOK)</span>
                              <input
                                className="panel__input"
                                type="password"
                                value={input.apiKey}
                                onChange={(event) =>
                                  handleLlmInputChange(
                                    provider.id,
                                    "apiKey",
                                    event.target.value,
                                  )
                                }
                                placeholder={
                                  summary?.configured ? "Saved" : "Paste API key"
                                }
                              />
                            </label>
                            <label className="panel__label">
                              <span>Validation key (BYOK)</span>
                              <input
                                className="panel__input"
                                type="password"
                                value={input.validationApiKey}
                                onChange={(event) =>
                                  handleLlmInputChange(
                                    provider.id,
                                    "validationApiKey",
                                    event.target.value,
                                  )
                                }
                                placeholder={
                                  summary?.configured ? "Saved (optional)" : "Paste API key"
                                }
                              />
                            </label>
                          </div>
                          <div className="panel__actions">
                            <button
                              type="button"
                              className="button button--primary-subtle"
                              onClick={() => void handleSaveLlmProvider(provider.id)}
                            >
                              Save provider
                            </button>
                            <button
                              type="button"
                              className="button button--ghost"
                              onClick={() => void handleActivateLlmProvider(provider.id)}
                              disabled={!summary?.chat_configured}
                            >
                              Use for chat
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </details>
              <details className="admin-ops__details">
                <summary>Agent skills</summary>
                {!userId ? (
                  <p className="panel__empty">Sign in to edit skills.</p>
                ) : (
                  <div className="admin__form">
                    <span className="panel__label">Skill</span>
                    <select
                      value={activeSkillName}
                      onChange={(event) => setActiveSkillName(event.target.value)}
                    >
                      {skillNames.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </select>
                    {activeSkill?.updated_at ? (
                      <p className="panel__meta">Updated: {activeSkill.updated_at}</p>
                    ) : null}
                    <input
                      type="text"
                      placeholder="Description"
                      value={skillDescription}
                      onChange={(event) => setSkillDescription(event.target.value)}
                    />
                    <input
                      type="text"
                      placeholder="Version"
                      value={skillVersion}
                      onChange={(event) => setSkillVersion(event.target.value)}
                    />
                    <label className="panel__label panel__label--inline">
                      <input
                        type="checkbox"
                        checked={skillEnabled}
                        onChange={(event) => setSkillEnabled(event.target.checked)}
                      />
                      Enabled
                    </label>
                    <textarea
                      rows={10}
                      value={skillContent}
                      onChange={(event) => setSkillContent(event.target.value)}
                    />
                    {skillHistory.length > 0 ? (
                      <div className="admin__history">
                        <span className="panel__label">Recent versions</span>
                        <ul className="admin__list">
                          {skillHistory.map((item) => (
                            <li key={item.id}>
                              <span>{item.version ?? "n/a"}</span>
                              <span className="admin__meta">{item.changed_at ?? ""}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {skillError ? <p className="panel__error">{skillError}</p> : null}
                    {skillSaved ? <p className="panel__success">Saved skill.</p> : null}
                    <button
                      type="button"
                      className="button button--primary-subtle"
                      onClick={handleSaveSkill}
                    >
                      Save skill
                    </button>
                  </div>
                )}
              </details>
              <details className="admin-ops__details">
                <summary>Learning loop maintenance</summary>
                {!userId ? (
                  <p className="panel__empty">Sign in to run maintenance.</p>
                ) : (
                  <div className="admin__form">
                    <p className="panel__meta">
                      Refresh calibration profiles and distill high-confidence belief memory.
                    </p>
                    <div className="panel__grid">
                      <label className="panel__label">
                        <span>Client scope</span>
                        <input
                          className="panel__input panel__input--neutral"
                          type="text"
                          readOnly
                          value={activeClientId || "all clients"}
                        />
                      </label>
                      <label className="panel__label">
                        <span>Lookback days</span>
                        <input
                          className="panel__input panel__input--neutral"
                          type="number"
                          min={1}
                          max={365}
                          value={loopMaintenanceLookbackDays}
                          onChange={(event) =>
                            setLoopMaintenanceLookbackDays(event.target.value)
                          }
                        />
                      </label>
                      <label className="panel__label">
                        <span>Min confidence</span>
                        <input
                          className="panel__input panel__input--neutral"
                          type="number"
                          min={0}
                          max={1}
                          step={0.05}
                          value={loopMaintenanceMinConfidence}
                          onChange={(event) =>
                            setLoopMaintenanceMinConfidence(event.target.value)
                          }
                        />
                      </label>
                    </div>
                    <div className="panel__actions">
                      <button
                        type="button"
                        className="button button--primary-subtle"
                        onClick={() => void handleRunLoopMaintenance()}
                        disabled={loopMaintenanceRunning}
                      >
                        {loopMaintenanceRunning ? "Running..." : "Run maintenance"}
                      </button>
                    </div>
                    {loopMaintenanceError ? (
                      <p className="panel__error">{loopMaintenanceError}</p>
                    ) : null}
                    {loopMaintenanceResult ? (
                      <div className="admin__history">
                        <span className="panel__label">Last run summary</span>
                        <ul className="admin__list">
                          {loopMaintenanceResult.results.map((item) => (
                            <li key={item.client_id}>
                              <span>{item.client_id}</span>
                              <span className="admin__meta">
                                calibration {item.calibration_profiles_updated} · distilled{" "}
                                {item.memory_artifacts_distilled}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    <div className="admin__history">
                      <span className="panel__label">Recent runs</span>
                      {loopMaintenanceHistory.length === 0 ? (
                        <p className="panel__meta">No maintenance runs logged yet.</p>
                      ) : (
                        <ul className="admin__list">
                          {loopMaintenanceHistory.map((item) => (
                            <li key={item.id}>
                              <span>
                                {item.created_at ?? "n/a"} · lookback {item.lookback_days}d ·
                                min conf {item.min_confidence}
                              </span>
                              <span className="admin__meta">
                                calibration {item.calibration_profiles_updated} · distilled{" "}
                                {item.memory_artifacts_distilled}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}
              </details>
            </section>
            {isCreateClientDrawerOpen && (
              <div
                className="admin-onboarding__drawer-overlay"
                onClick={() => {
                  if (createClientBusy) return;
                  setCreateClientDrawerOpen(false);
                }}
              >
                <aside
                  className="admin-onboarding__drawer"
                  onClick={(event) => event.stopPropagation()}
                >
                  <div className="panel__header">
                    <h3>Add new client</h3>
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => setCreateClientDrawerOpen(false)}
                      disabled={createClientBusy}
                    >
                      Close
                    </button>
                  </div>
                  <p className="panel__meta">
                    Creates one client, one initial brand, a product list, and canonical/UCP/ACP metadata in one flow.
                  </p>
                  <div className="admin__form">
                    <span className="panel__label">Client</span>
                    <input
                      type="text"
                      placeholder="client-id"
                      value={newClientForm.clientId}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          clientId: event.target.value,
                        }))
                      }
                    />
                    <input
                      type="text"
                      placeholder="Client name"
                      value={newClientForm.clientName}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          clientName: event.target.value,
                        }))
                      }
                    />

                    <span className="panel__label">Initial brand</span>
                    <input
                      type="text"
                      placeholder="brand-id"
                      value={newClientForm.brandId}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          brandId: event.target.value,
                        }))
                      }
                    />
                    <input
                      type="text"
                      placeholder="Brand name"
                      value={newClientForm.brandName}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          brandName: event.target.value,
                        }))
                      }
                    />

                    <span className="panel__label">Products list</span>
                    <textarea
                      rows={5}
                      placeholder={"product-id|Product name|Short description\nproduct-id-2|Product 2|Short description"}
                      value={newClientForm.productsText}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          productsText: event.target.value,
                        }))
                      }
                    />

                    <span className="panel__label">Canonical intent spec</span>
                    <p className="panel__meta">
                      Category and use cases are required. Choose a category first to load ontology options.
                    </p>
                    <label className="panel__label">Category</label>
                    <select
                      value={newClientForm.category}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          category: event.target.value,
                          subCategory: "",
                        }))
                      }
                    >
                      <option value="">Select category</option>
                      {Object.entries(canonicalOntology).map(([key, value]) => (
                        <option key={key} value={key}>
                          {value.label}
                        </option>
                      ))}
                    </select>
                    <label className="panel__label">Sub category</label>
                    <select
                      value={newClientForm.subCategory}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          subCategory: event.target.value,
                        }))
                      }
                    >
                      <option value="">Select sub category</option>
                      {(onboardingOntology?.subCategories ?? []).map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <label className="panel__label">Use cases</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, onboardingUseCases.length || 3))}
                      value={parseCsv(newClientForm.useCases)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setNewClientForm((current) => ({
                          ...current,
                          useCases: selected.join(", "),
                        }));
                      }}
                    >
                      {onboardingUseCases.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: daily_training, long_distance, speed_work
                    </p>
                    <label className="panel__label">Audience archetypes</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, onboardingArchetypes.length || 3))}
                      value={parseCsv(newClientForm.archetypes)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setNewClientForm((current) => ({
                          ...current,
                          archetypes: selected.join(", "),
                        }));
                      }}
                    >
                      {onboardingArchetypes.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: beginner_runner, performance_runner
                    </p>
                    <label className="panel__label">Feature concepts</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, onboardingFeatures.length || 3))}
                      value={parseCsv(newClientForm.featureConcepts)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setNewClientForm((current) => ({
                          ...current,
                          featureConcepts: selected.join(", "),
                        }));
                      }}
                    >
                      {onboardingFeatures.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: cushioning, stability, breathability
                    </p>
                    <label className="panel__label">Core constraints</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, onboardingConstraints.length || 3))}
                      value={parseCsv(newClientForm.constraints)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setNewClientForm((current) => ({
                          ...current,
                          constraints: selected.join(", "),
                        }));
                      }}
                    >
                      {onboardingConstraints.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: budget_sensitive, availability_required
                    </p>
                    <label className="panel__label">Must-not-target segments</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, onboardingExclusions.length || 3))}
                      value={parseCsv(newClientForm.exclusions)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setNewClientForm((current) => ({
                          ...current,
                          exclusions: selected.join(", "),
                        }));
                      }}
                    >
                      {onboardingExclusions.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: elite_racer_only, non_sport_use
                    </p>
                    <textarea
                      rows={2}
                      placeholder="Objective keywords (optional, comma separated)"
                      value={newClientForm.objectiveKeywords}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          objectiveKeywords: event.target.value,
                        }))
                      }
                    />
                    <textarea
                      rows={2}
                      placeholder="Banned keywords (optional, comma separated)"
                      value={newClientForm.bannedKeywords}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          bannedKeywords: event.target.value,
                        }))
                      }
                    />

                    <span className="panel__label">UCP defaults (optional)</span>
                    <input
                      type="url"
                      placeholder="Offer URL"
                      value={newClientForm.ucpOfferUrl}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          ucpOfferUrl: event.target.value,
                        }))
                      }
                    />
                    <input
                      type="text"
                      placeholder="Merchant name"
                      value={newClientForm.ucpMerchantName}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          ucpMerchantName: event.target.value,
                        }))
                      }
                    />
                    <input
                      type="text"
                      placeholder="Currency"
                      value={newClientForm.ucpCurrency}
                      onChange={(event) =>
                        setNewClientForm((current) => ({
                          ...current,
                          ucpCurrency: event.target.value,
                        }))
                      }
                    />

                    <span className="panel__label">ACP defaults</span>
                    <label className="panel__label panel__label--inline">
                      <input
                        type="checkbox"
                        checked={newClientForm.acpEnableSearch}
                        onChange={(event) =>
                          setNewClientForm((current) => ({
                            ...current,
                            acpEnableSearch: event.target.checked,
                          }))
                        }
                      />
                      Enable search
                    </label>
                    <label className="panel__label panel__label--inline">
                      <input
                        type="checkbox"
                        checked={newClientForm.acpEnableCheckout}
                        onChange={(event) =>
                          setNewClientForm((current) => ({
                            ...current,
                            acpEnableCheckout: event.target.checked,
                          }))
                        }
                      />
                      Enable checkout
                    </label>

                    {createClientError ? <p className="panel__error">{createClientError}</p> : null}
                    {createClientSuccess ? <p className="panel__success">{createClientSuccess}</p> : null}
                    <button
                      type="button"
                      className="button button--primary-subtle"
                      onClick={() => void handleCreateClientOnboarding()}
                      disabled={!canSubmitNewClient || createClientBusy}
                    >
                      {createClientBusy ? "Creating..." : "Create client onboarding"}
                    </button>
                  </div>
                </aside>
              </div>
            )}
            {isIntentDrawerOpen && (
              <div
                className="admin-onboarding__drawer-overlay"
                onClick={() => setIntentDrawerOpen(false)}
              >
                <aside
                  className="admin-onboarding__drawer"
                  onClick={(event) => event.stopPropagation()}
                >
                  <div className="panel__header">
                    <h3>Canonical intent spec</h3>
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => setIntentDrawerOpen(false)}
                    >
                      Close
                    </button>
                  </div>
                  <p className="panel__meta">
                    Scope: {selectedClient?.name ?? "No client"} /{" "}
                    {selectedBrand?.name ?? "No brand"} /{" "}
                    {selectedProduct?.name ?? "No product"}
                  </p>
                  <div className="admin__form">
                    <div className="panel__row panel__row--compact">
                      <button
                        type="button"
                        className="button button--ghost"
                        onClick={() => void handleAutofillIntentSpec("preview")}
                        disabled={!selectedProduct}
                      >
                        Preview UCP/ACP autofill
                      </button>
                      <button
                        type="button"
                        className="button button--primary-subtle"
                        onClick={() => void handleAutofillIntentSpec("apply")}
                        disabled={!selectedProduct}
                      >
                        Apply autofill
                      </button>
                    </div>
                    <label className="panel__label">Category (required)</label>
                    <p className="panel__meta">
                      Choose category first. Use cases are required for bottom-up query generation.
                    </p>
                    <select
                      value={intentSpecForm.category}
                      onChange={(event) =>
                        setIntentSpecForm((current) => ({
                          ...current,
                          category: event.target.value,
                          subCategory: "",
                        }))
                      }
                    >
                      <option value="">Select category</option>
                      {Object.entries(canonicalOntology).map(([key, value]) => (
                        <option key={key} value={key}>
                          {value.label}
                        </option>
                      ))}
                    </select>
                    <label className="panel__label">Sub category</label>
                    <select
                      value={intentSpecForm.subCategory}
                      onChange={(event) =>
                        setIntentSpecForm((current) => ({
                          ...current,
                          subCategory: event.target.value,
                        }))
                      }
                    >
                      <option value="">Select sub category</option>
                      {(selectedOntology?.subCategories ?? []).map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <label className="panel__label">Use cases (ontology)</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, ontologyUseCases.length || 3))}
                      value={parseCsv(intentSpecForm.useCases)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setIntentSpecForm((current) => ({
                          ...current,
                          useCases: selected.join(", "),
                        }));
                      }}
                    >
                      {ontologyUseCases.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: daily_training, long_distance, speed_work
                    </p>
                    <label className="panel__label">Audience archetypes (ontology)</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, ontologyArchetypes.length || 3))}
                      value={parseCsv(intentSpecForm.archetypes)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setIntentSpecForm((current) => ({
                          ...current,
                          archetypes: selected.join(", "),
                        }));
                      }}
                    >
                      {ontologyArchetypes.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: beginner_runner, performance_runner
                    </p>
                    <label className="panel__label">Feature concepts (ontology)</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, ontologyFeatureConcepts.length || 3))}
                      value={parseCsv(intentSpecForm.featureConcepts)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setIntentSpecForm((current) => ({
                          ...current,
                          featureConcepts: selected.join(", "),
                        }));
                      }}
                    >
                      {ontologyFeatureConcepts.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: cushioning, stability, breathability
                    </p>
                    <label className="panel__label">Core constraints</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, ontologyConstraints.length || 3))}
                      value={parseCsv(intentSpecForm.constraints)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setIntentSpecForm((current) => ({
                          ...current,
                          constraints: selected.join(", "),
                        }));
                      }}
                    >
                      {ontologyConstraints.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: budget_sensitive, availability_required
                    </p>
                    <label className="panel__label">Must-not-target segments</label>
                    <select
                      multiple
                      size={Math.min(6, Math.max(3, ontologyExclusions.length || 3))}
                      value={parseCsv(intentSpecForm.exclusions)}
                      onChange={(event) => {
                        const selected = Array.from(event.target.selectedOptions).map(
                          (option) => option.value,
                        );
                        setIntentSpecForm((current) => ({
                          ...current,
                          exclusions: selected.join(", "),
                        }));
                      }}
                    >
                      {ontologyExclusions.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="panel__meta">
                      Example: elite_racer_only, non_sport_use
                    </p>
                    <textarea
                      rows={2}
                      placeholder="Objective keywords (optional, comma separated)"
                      value={intentSpecForm.objectiveKeywords}
                      onChange={(event) =>
                        setIntentSpecForm((current) => ({
                          ...current,
                          objectiveKeywords: event.target.value,
                        }))
                      }
                    />
                    <textarea
                      rows={2}
                      placeholder="Banned keywords (optional, comma separated)"
                      value={intentSpecForm.bannedKeywords}
                      onChange={(event) =>
                        setIntentSpecForm((current) => ({
                          ...current,
                          bannedKeywords: event.target.value,
                        }))
                      }
                    />
                    <button
                      type="button"
                      className="button button--primary-subtle"
                      onClick={handleSaveIntentSpec}
                      disabled={!canSaveIntentSpec}
                    >
                      Save intent spec
                    </button>
                  </div>
                </aside>
              </div>
            )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
