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
  low_confidence?: boolean;
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
    low_confidence?: boolean;
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

export type SimulationProduct = {
  id: string;
  name: string;
  description: string;
  source?: string;
  url?: string;
  price?: number;
  confidence?: number;
  metadata?: Record<string, unknown>;
};

export type SimulationGapReport = {
  product_id: string;
  goal: string;
  score: number;
  matched_signals: string[];
  missing_signals: string[];
  severity: string;
  summary: string;
};

export type SimulationRunResponse = {
  run_id: string;
  result: {
    intent?: ConversationResponse["intent"];
    goals: string[];
    scores: {
      product_id: string;
      score: number;
      alignment_reasoning?: string;
      matched_capabilities?: string[];
      confidence?: number;
      low_confidence?: boolean;
    }[];
    winner_id?: string | null;
    gap_analysis: SimulationGapReport[];
    profiles: {
      product_id?: string;
      capabilities_enabled?: string[];
      goals_served?: string[];
      prerequisites?: string[];
      outcomes_expected?: string[];
      context_fit?: Record<string, number>;
    }[];
  };
};

export type SimulationOptimizeResponse = {
  run_id: string;
  optimized: {
    id: string;
    name: string;
    before: string;
    after: string;
  };
  gap: SimulationGapReport;
};

export type SimulationRetestResponse = {
  run_id: string;
  result: SimulationRunResponse["result"];
};

export type SimulationRunSummary = {
  id: string;
  query: string;
  created_at?: string;
  winner_id?: string | null;
};

export type SimulationRunListResponse = {
  runs: SimulationRunSummary[];
};

export type SimulationRunDetailResponse = {
  run: {
    id: string;
    query: string;
    created_at?: string;
    products: SimulationProduct[];
    result: SimulationRunResponse["result"];
    retest?: SimulationRunResponse["result"] | null;
  };
};

export type ConversationResponse = {
  session_id: string;
  user_id: string;
  snapshot?: {
    session: {
      id: string;
      user_id?: string;
      created_at?: string;
      state?: Record<string, unknown>;
    };
    turns?: {
      id?: number;
      session_id?: string;
      speaker: "user" | "agent";
      content: string;
      created_at?: string;
      metadata?: Record<string, unknown>;
    }[];
    goals?: string[];
    semantic_goals?: string[];
    latest_episode?: Record<string, unknown> | null;
  };
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

export type SessionSummary = {
  id: string;
  created_at?: string;
  preview?: string;
  last_turn_at?: string;
};

export type SessionListResponse = {
  sessions: SessionSummary[];
};

export type ResearchRefreshResponse = {
  query?: string;
  goals?: string[];
  research_results: Product[];
  updated_at?: string;
};
