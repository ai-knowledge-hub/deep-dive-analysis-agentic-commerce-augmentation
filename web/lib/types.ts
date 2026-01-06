export type ClarificationState = {
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
  reasoning?: string;
};

export type ConversationResponse = {
  session_id: string;
  user_id: string;
  plan?: {
    query?: string;
    products?: Product[];
    clarifications?: string[];
    world_a_example?: string;
    empowerment?: {
      goal_alignment?: {
        score?: number;
        aligned_goals?: string[];
        misaligned_goals?: string[];
      };
    };
  };
  clarification?: string;
  values_state?: ClarificationState;
  product_explanations?: {
    id?: string;
    name?: string;
    reasoning?: string;
    capabilities_enabled?: string[];
    confidence?: number;
  }[];
  explanation?: string;
  reflection?: string;
  guardrails?: Record<string, unknown>;
};
