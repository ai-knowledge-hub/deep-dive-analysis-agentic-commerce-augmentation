"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAppUser } from "../../lib/auth";
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
import { AgentSkillsPanel } from "../../components/admin/AgentSkillsPanel";
import { CanonicalIntentSpecDrawer } from "../../components/admin/CanonicalIntentSpecDrawer";
import { Sidebar } from "../../components/layout/Sidebar";
import { DetailHeader } from "../../components/layout/DetailHeader";
import { HistoryDrawer } from "../../components/layout/HistoryDrawer";
import { useTenant } from "../../components/tenant/TenantProvider";
import { AdminOnboardingWorkspace } from "../../components/admin/AdminOnboardingWorkspace";
import { BrandSetupPanel } from "../../components/admin/BrandSetupPanel";
import { CanonicalIntentSpecPanel } from "../../components/admin/CanonicalIntentSpecPanel";
import { ClientAccessPanel } from "../../components/admin/ClientAccessPanel";
import { CreateClientOnboardingDrawer } from "../../components/admin/CreateClientOnboardingDrawer";
import { LearningLoopMaintenancePanel } from "../../components/admin/LearningLoopMaintenancePanel";
import { ModelGatewayPanel } from "../../components/admin/ModelGatewayPanel";
import { OnboardingReviewPanel } from "../../components/admin/OnboardingReviewPanel";
import { PlatformProfilePanel } from "../../components/admin/PlatformProfilePanel";
import { ProductCatalogPanel } from "../../components/admin/ProductCatalogPanel";

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
  const { user } = useAppUser();
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

  const onboardingFlowSteps = useMemo(
    () => [
      { id: 1, label: "Select scope", done: onboardingCompletion.doneClient },
      { id: 2, label: "Create brand", done: onboardingCompletion.doneBrand },
      { id: 3, label: "Create product", done: onboardingCompletion.doneProduct },
      { id: 4, label: "Define canonical intent", done: onboardingCompletion.doneIntent },
    ],
    [onboardingCompletion],
  );

  const onboardingCurrentStep = useMemo(
    () => onboardingFlowSteps.find((step) => !step.done)?.id ?? onboardingFlowSteps.length,
    [onboardingFlowSteps],
  );

  const onboardingNextAction = useMemo(() => {
    if (!onboardingCompletion.doneClient) {
      return {
        label: "Add a client",
        helper: "Start by creating a client workspace and initial catalog shell.",
        action: "client" as const,
      };
    }
    if (!onboardingCompletion.doneBrand) {
      return {
        label: "Add a brand",
        helper: "Create at least one brand under the selected client.",
        action: "brand" as const,
      };
    }
    if (!onboardingCompletion.doneProduct) {
      return {
        label: "Add a product",
        helper: "Create the first product to enable intent spec and query generation.",
        action: "product" as const,
      };
    }
    if (!onboardingCompletion.doneIntent) {
      return {
        label: "Define canonical intent spec",
        helper: "Set category + use cases so bottom-up generation can run reliably.",
        action: "intent" as const,
      };
    }
    return {
      label: "Onboarding complete",
      helper: "You can now move to Experiments or configure advanced operations.",
      action: "complete" as const,
    };
  }, [onboardingCompletion]);

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

  const handleRunOnboardingNextAction = useCallback(() => {
    switch (onboardingNextAction.action) {
      case "client":
        setCreateClientDrawerOpen(true);
        setCreateClientError(null);
        setCreateClientSuccess(null);
        return;
      case "brand":
        setShowCreateBrand(true);
        return;
      case "product":
        setShowCreateProduct(true);
        return;
      case "intent":
        setIntentDrawerOpen(true);
        return;
      default:
        return;
    }
  }, [onboardingNextAction.action]);

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
        onNewConversation={() => router.push("/lab")}
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
          <DetailHeader title="Admin" onMenu={() => setSidebarOpen(true)} onBack={() => router.push("/lab")} />
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
            <AdminOnboardingWorkspace
              completion={onboardingCompletion}
              currentStep={onboardingCurrentStep}
              flowSteps={onboardingFlowSteps}
              nextAction={onboardingNextAction}
              activeClientId={activeClientId}
              activeBrandId={activeBrandId}
              activeProductId={activeProductId}
              clients={clients}
              brands={brands}
              products={products}
              onRunNextAction={handleRunOnboardingNextAction}
              onClientChange={(nextClientId) => {
                setActiveClientId(nextClientId);
                setTenantClientId(nextClientId || "");
                setActiveBrandId("");
                setActiveProductId("");
              }}
              onBrandChange={(nextBrandId) => {
                setActiveBrandId(nextBrandId);
                setTenantBrandId(nextBrandId || null);
                setActiveProductId("");
              }}
              onProductChange={(nextProductId) => {
                setActiveProductId(nextProductId);
                setTenantProductId(nextProductId || null);
              }}
              onAddClient={() => {
                setCreateClientDrawerOpen(true);
                setCreateClientError(null);
                setCreateClientSuccess(null);
              }}
            >
                <ClientAccessPanel
                  activeClientId={activeClientId}
                  selectedClientName={selectedClient?.name}
                  clientUsers={clientUsers}
                  userForm={userForm}
                  onUserFormChange={(patch) =>
                    setUserForm((current) => ({ ...current, ...patch }))
                  }
                  onAddClientUser={handleAddClientUser}
                />
                <BrandSetupPanel
                  activeClientId={activeClientId}
                  selectedClientName={selectedClient?.name}
                  brands={brands}
                  showCreateBrand={showCreateBrand}
                  brandForm={brandForm}
                  canCreateBrand={canCreateBrand}
                  onShowCreateBrandChange={setShowCreateBrand}
                  onBrandFormChange={(patch) =>
                    setBrandForm((current) => ({ ...current, ...patch }))
                  }
                  onCreateBrand={handleCreateBrand}
                />
                <ProductCatalogPanel
                  activeBrandId={activeBrandId}
                  selectedBrandName={selectedBrand?.name}
                  products={products}
                  showCreateProduct={showCreateProduct}
                  productForm={productForm}
                  canCreateProduct={canCreateProduct}
                  onShowCreateProductChange={setShowCreateProduct}
                  onProductFormChange={(patch) =>
                    setProductForm((current) => ({ ...current, ...patch }))
                  }
                  onCreateProduct={handleCreateProduct}
                >
                  <PlatformProfilePanel
                    platformProfile={platformProfile}
                    profileName={platformProfileName}
                    profileVersion={platformProfileVersion}
                    profileText={platformProfileText}
                    profileError={platformProfileError}
                    profileSaved={platformProfileSaved}
                    onProfileNameChange={setPlatformProfileName}
                    onProfileVersionChange={setPlatformProfileVersion}
                    onProfileTextChange={setPlatformProfileText}
                    onSaveProfile={handleSavePlatformProfile}
                  />
                </ProductCatalogPanel>
                <CanonicalIntentSpecPanel
                  canOpenIntentEditor={Boolean(selectedProduct)}
                  intentSpecSaved={intentSpecSaved}
                  intentSpecAutofillStatus={intentSpecAutofillStatus}
                  intentSpecError={intentSpecError}
                  onOpenIntentEditor={() => setIntentDrawerOpen(true)}
                />
                <OnboardingReviewPanel
                  onboardingCompletion={onboardingCompletion}
                  canOpenIntentEditor={Boolean(selectedProduct)}
                  onAddClient={() => {
                    setCreateClientDrawerOpen(true);
                    setCreateClientError(null);
                    setCreateClientSuccess(null);
                  }}
                  onAddBrand={() => setShowCreateBrand(true)}
                  onAddProduct={() => setShowCreateProduct(true)}
                  onOpenIntentEditor={() => setIntentDrawerOpen(true)}
                />
            </AdminOnboardingWorkspace>

            <section className="panel__card admin-ops">
              <div className="panel__header">
                <h3>Operational controls</h3>
              </div>
              <p className="panel__subheading">Advanced operations</p>
              <p className="panel__step-helper">
                These controls tune providers, skills, and maintenance after onboarding is complete.
              </p>
              <ModelGatewayPanel
                userId={userId}
                llmConfig={llmConfig}
                llmConfigError={llmConfigError}
                llmInputs={llmInputs}
                providers={LLM_PROVIDERS}
                modelOptions={LLM_MODEL_OPTIONS}
                onInputChange={handleLlmInputChange}
                onSaveProvider={handleSaveLlmProvider}
                onActivateProvider={handleActivateLlmProvider}
              />
              <AgentSkillsPanel
                userId={userId}
                skillNames={skillNames}
                activeSkillName={activeSkillName}
                activeSkill={activeSkill}
                skillDescription={skillDescription}
                skillVersion={skillVersion}
                skillContent={skillContent}
                skillEnabled={skillEnabled}
                skillHistory={skillHistory}
                skillError={skillError}
                skillSaved={skillSaved}
                onActiveSkillNameChange={setActiveSkillName}
                onSkillDescriptionChange={setSkillDescription}
                onSkillVersionChange={setSkillVersion}
                onSkillContentChange={setSkillContent}
                onSkillEnabledChange={setSkillEnabled}
                onSaveSkill={handleSaveSkill}
              />
              <LearningLoopMaintenancePanel
                userId={userId}
                activeClientId={activeClientId}
                isRunning={loopMaintenanceRunning}
                error={loopMaintenanceError}
                result={loopMaintenanceResult}
                history={loopMaintenanceHistory}
                lookbackDays={loopMaintenanceLookbackDays}
                minConfidence={loopMaintenanceMinConfidence}
                onLookbackDaysChange={setLoopMaintenanceLookbackDays}
                onMinConfidenceChange={setLoopMaintenanceMinConfidence}
                onRunMaintenance={handleRunLoopMaintenance}
              />
            </section>
            <CreateClientOnboardingDrawer
              isOpen={isCreateClientDrawerOpen}
              isBusy={createClientBusy}
              canSubmit={canSubmitNewClient}
              error={createClientError}
              success={createClientSuccess}
              form={newClientForm}
              currentClientName={selectedClient?.name}
              currentBrandName={selectedBrand?.name}
              currentProductName={selectedProduct?.name}
              canonicalOntology={canonicalOntology}
              selectedOntology={onboardingOntology}
              useCases={onboardingUseCases}
              archetypes={onboardingArchetypes}
              featureConcepts={onboardingFeatures}
              constraints={onboardingConstraints}
              exclusions={onboardingExclusions}
              onClose={() => setCreateClientDrawerOpen(false)}
              onFormChange={(patch) =>
                setNewClientForm((current) => ({ ...current, ...patch }))
              }
              onSubmit={handleCreateClientOnboarding}
            />
            <CanonicalIntentSpecDrawer
              isOpen={isIntentDrawerOpen}
              canAutofill={Boolean(selectedProduct)}
              canSave={canSaveIntentSpec}
              form={intentSpecForm}
              currentClientName={selectedClient?.name}
              currentBrandName={selectedBrand?.name}
              currentProductName={selectedProduct?.name}
              canonicalOntology={canonicalOntology}
              selectedOntology={selectedOntology}
              useCases={ontologyUseCases}
              archetypes={ontologyArchetypes}
              featureConcepts={ontologyFeatureConcepts}
              constraints={ontologyConstraints}
              exclusions={ontologyExclusions}
              onClose={() => setIntentDrawerOpen(false)}
              onFormChange={(patch) =>
                setIntentSpecForm((current) => ({ ...current, ...patch }))
              }
              onAutofill={handleAutofillIntentSpec}
              onSave={handleSaveIntentSpec}
            />
            </>
          )}
        </div>
      </main>
    </div>
  );
}
