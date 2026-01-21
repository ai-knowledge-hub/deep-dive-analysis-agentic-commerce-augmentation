export type GoalClarificationState = {
  query: string;
  turns: { speaker: string; content: string }[];
  extracted_goals: string[];
  ready_for_products: boolean;
  metadata: Record<string, unknown>;
};

export type Product = {
  id: string;
  name: string;
  price?: number;
  confidence?: number;
  source?: string;
  merchant_name?: string;
  offer_url?: string;
  capabilities_enabled?: string[];
  alignment_score?: number;
  alignment_reasoning?: string;
  description?: string;
  intentionality_profile?: {
    product_id?: string;
    capabilities_enabled?: string[];
    goals_served?: string[];
    prerequisites?: string[];
    outcomes_expected?: string[];
    context_fit?: Record<string, number>;
  };
  reasoning?: string;
};

export type EvidenceProduct = {
  id: string;
  name: string;
  description: string;
  source: string;
  url?: string;
  price?: number;
  confidence?: number;
  raw_text?: string;
  metadata?: Record<string, unknown>;
};

export type EvidenceAnalyzeResponse = {
  intent?: ConversationResponse["intent"];
  goals: string[];
  evidence_products: EvidenceProduct[];
  profiles: {
    product_id?: string;
    capabilities_enabled?: string[];
    goals_served?: string[];
    prerequisites?: string[];
    outcomes_expected?: string[];
    context_fit?: Record<string, number>;
  }[];
  alignment_scores: {
    product_id: string;
    score: number;
    matched_capabilities?: string[];
    alignment_reasoning?: string;
    confidence?: number;
  }[];
};

export type RepresentationOptimizeResponse = {
  intent?: ConversationResponse["intent"];
  goals: string[];
  optimized: {
    id: string;
    name: string;
    before: string;
    after: string;
    capabilities: string[];
    outcomes: string[];
    goals: string[];
  }[];
  alignment_deltas: {
    product_id: string;
    before: number;
    after: number;
    delta: number;
  }[];
};

export type RecommendationVerifyResponse = {
  intent?: ConversationResponse["intent"];
  goals: string[];
  predicted: string[];
  actual: string[];
  lift: number;
  baseline_alignment: {
    product_id: string;
    score: number;
  }[];
  optimized_alignment: {
    product_id: string;
    score: number;
  }[];
};

export type ConversationResponse = {
  session_id: string;
  user_id: string;
  intent?: {
    primary_goal?: string;
    secondary_goals?: string[];
    underlying_needs?: string[];
    context_signals?: string[];
    confidence?: number;
    domain?: string;
  };
  baseline_alignment?: number;
  plan?: {
    query?: string;
    products?: Product[];
    catalog_results?: Product[];
    research_results?: Product[];
    clarifications?: string[];
    alignment?: {
      goal_alignment?: {
        score?: number;
        baseline_score?: number;
        aligned_goals?: string[];
        misaligned_goals?: string[];
      };
      research?: {
        per_item?: {
          product_id?: string;
          score?: number;
          alignment_reasoning?: string;
        }[];
      };
    };
  };
  clarification?: string;
  goal_state?: GoalClarificationState;
  product_explanations?: {
    id?: string;
    name?: string;
    reasoning?: string;
    capabilities_enabled?: string[];
    confidence?: number;
  }[];
  explanation?: string;
  intentionality_profiles?: {
    product_id?: string;
    capabilities_enabled?: string[];
    goals_served?: string[];
    prerequisites?: string[];
    outcomes_expected?: string[];
    context_fit?: Record<string, number>;
  }[];
};
