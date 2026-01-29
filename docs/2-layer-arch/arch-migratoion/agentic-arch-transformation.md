# Agentic Architecture Transformation
## From Monolithic Modules to a Layered Agentic System (Inference + Protocol)

---

## Executive Summary

This document specifies the transformation of the current LLM Discoverability Simulation Sandbox from a **monolithic module architecture** to a **layered, agentic system** where:

1. **Layer 1 Agent** handles inference-based discovery (web crawling, semantic matching)
2. **Layer 2 Agent** handles protocol-based discovery (ACP/UCP, structured feeds)
3. **Orchestrator Agent** (optional) coordinates and critiques their outputs
4. Each agent operates with a **minimal harness** for tool execution, observation logging, and context/memory packaging
5. Clean Architecture principles ensure modularity and scalability (Domain → Application → Infrastructure)
6. Full RL-style learning and Bayesian belief objects everywhere are treated as **future experiments** once we have enough calibration data

**Key Insight**: “Agentic” is only valuable if it improves measurable outcomes (prediction accuracy, time-to-insight, optimization quality). This transformation prioritizes **replayability + observability first**, and evolves toward more advanced inference/action loops later.

---

## Reader Guide: What We Implement Now vs Later

**Implement now (Phase 0–3, hackathon-friendly):**
- Clean Architecture boundaries (`domain/`, `application/`, `infrastructure/`). The legacy `modules/` layout has been fully removed after migration.
- Minimal agent harness as a **tool/observation loop**:
  - tool registry + executor
  - replay logging (inputs/outputs/tools/timings/versions)
  - context packaging (token budget policies, caching)
- Layer routing that is **deterministic and inspectable** (rule-based or confidence-based), not “mystical orchestration”.

**Defer (future experiments once we have verified outcomes + calibration data):**
- Full RL environment semantics (rewards, policies, exploration).
- Bayesian belief objects as first-class state “everywhere”.
- Active inference style action selection based on information gain.

## What “Agentic” Means Here (Measurable)

We call the system “agentic” when it can:
- Run a tool/observation loop (retrieve → observe → refine → decide)
- Persist a reproducible run record (inputs, outputs, versions, timing)
- Route between Layer 1 (inference/web) and Layer 2 (protocol/feeds) deterministically when needed

**Non-goals for this phase (future research):**
- Full reinforcement learning (rewards, policy training, exploration)
- Probabilistic belief objects everywhere (Bayesian world models in every component)

---

## Current Architecture (Post-Migration)

### Directory Structure
```
application/agents/   # Agent harness + Layer 1/2 agents
infrastructure/llm/   # LLM API clients + gateway
shared/llm/           # Prompt templates

domain/               # Pure types + pure functions (no IO)
application/          # Use-cases / orchestration services
infrastructure/       # IO boundaries (DB/LLM/adapters)
```

### Current Flow (Monolithic)
```
User Query
    ↓
API Endpoint (FastAPI)
    ↓
Orchestrator (gateway.py)
    ↓
Modules (intent → intentionality → alignment → simulation)
    ↓
LLM Client (makes LLM calls)
    ↓
Response
```

**Problems with current architecture**:
1. **Monolithic execution**: All logic runs in single process, no agent autonomy
2. **Mixed concerns**: domain logic, LLM prompts, and DB operations are interleaved
3. **No tool loop**: tool calls aren’t logged as observations; debugging is hard
4. **No replayability**: runs aren’t fully reproducible (prompt/model versions not captured)
5. **No layer separation**: Layer 1 vs Layer 2 discovery isn’t enforced as a boundary
6. **Limited context management**: no explicit context window policy or caching strategy

---

## Target Architecture (To-Be)

### High-Level System

```
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION ORCHESTRATOR                     │
│  Coordinates the end-to-end flow for API/UI use-cases             │
│  (SimulationService, EvidenceService, VerificationService, etc.)  │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────────┐ ┌─────────────────────────────┐
│     LAYER 1 AGENT           │ │     LAYER 2 AGENT           │
│  (Inference/Web Discovery)  │ │  (Protocol/Feed Discovery)  │
│                             │ │                             │
│  Tools:                     │ │  Tools:                     │
│  - infer_intent             │ │  - query_acp_feed (mock/real)│
│  - retrieve_evidence        │ │  - query_ucp_discovery       │
│  - normalize_evidence       │ │  - validate_feed_schema      │
│  - score_semantic_match     │ │  - score_structured_match    │
└─────────────────────────────┘ └─────────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MINIMAL AGENT HARNESS                         │
│  - Tool execution + observation logging                           │
│  - Context builder (token budget policies)                         │
│  - Memory adapter (working/episodic/semantic)                      │
│  - Replay metadata (model/prompt/scoring versions)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DOMAIN LAYER (CORE)                         │
│  Pure business logic (no infrastructure dependencies)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                            │
│  LLM clients, DB repositories, external APIs/adapters             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Clean Architecture Mapping

### Dependency Rule
```
Infrastructure → Application → Domain
       ↓              ↑
   Adapters        Agents (optional strategy modules)
```

**Core Principle**: Domain logic is **pure** and has **no dependencies on infrastructure**. Application coordinates system flows. Agents are optional strategy modules that call application services/tools.

---

## Migration Strategy (Strangler Pattern)

This transformation must be **incremental** to avoid freezing feature work (protocol simulation + verification are urgent).

1. **Introduce `domain/` and `application/`**
   - The codebase now routes behavior through `domain/` + `application/` with IO in `infrastructure/`.
2. **Move pure functions first**
   - Alignment scoring, gap analysis, phrase matching, normalization.
3. **Create application services**
   - `SimulationService`, `EvidenceService`, `AdminService`, `VerificationService`.
4. **Add harness logging + replay metadata**
   - Persist run inputs/outputs + version identifiers.
5. **Only then introduce Layer 1/Layer 2 agents**
   - Start as a router and tool-loop wrapper around existing services.

---

## Observability & Replay (Required)

Every simulation/verification run must record:
- `provider/model`, prompt version, scoring version
- tool calls + timings
- predicted winner vs verified winner (if verification exists)
- tenant scope (`client_id`, optional `brand_id`/`product_id`)

This enables debugging, evaluation, and future calibration.

---

## Future Experiments (After Data)

Once we have enough verified outcomes:
- Reinforcement learning style optimization loops (reward signals + policies)
- Rich Bayesian belief objects maintained across steps (world-model beliefs)
- Automated scoring calibration (learn weights from prediction vs reality)

### Layer Breakdown

#### **1. Domain Layer (Core Business Logic)**
Location: `domain/`

```
domain/
├── __init__.py
├── entities/              # Core data structures
│   ├── intent.py          # InferredIntent, IntentSignals
│   ├── product.py         # Product, IntentionalityProfile
│   ├── alignment.py       # AlignmentScore
│   └── evidence.py        # EvidenceItem, EvidenceProfile
│
├── use_cases/            # Business logic operations
│   ├── infer_intent.py   # Intent inference (Bayesian optional later)
│   ├── profile_product.py # Intentionality mapping
│   ├── score_alignment.py # Alignment calculation
│   ├── analyze_evidence.py # Evidence analysis
│   └── simulate_discovery.py # Simulation logic
│
├── repositories/         # Abstract interfaces (no implementation)
│   ├── product_repository.py
│   ├── memory_repository.py
│   ├── llm_repository.py
│   └── evidence_repository.py
│
└── value_objects/        # Immutable values
    ├── confidence.py     # Confidence scores
    ├── capability.py     # Capability descriptors
    └── context.py        # Context objects
```

**Example: Bayesian Intent Inference (Future Experiment Sketch)**

This section is an *optional* future direction. Do not block Phase 0–3 on this;
start with the existing intent inference + calibration metrics and upgrade later.
```python
# domain/use_cases/infer_intent.py

from dataclasses import dataclass
from typing import List, Dict
import math

@dataclass
class PriorBelief:
    """Prior probability distribution over intent hypotheses"""
    hypotheses: Dict[str, float]  # intent_label -> probability
    
    def __post_init__(self):
        # Normalize to sum to 1.0
        total = sum(self.hypotheses.values())
        if total > 0:
            self.hypotheses = {k: v/total for k, v in self.hypotheses.items()}

@dataclass
class Evidence:
    """Observable signals from user query/context"""
    query_text: str
    context_signals: List[str]
    constraints: List[str]
    
@dataclass
class Likelihood:
    """P(Evidence | Intent) - how likely is this evidence given each intent"""
    scores: Dict[str, float]  # intent_label -> likelihood

class BayesianIntentInference:
    """Pure Bayesian belief updating - no LLM calls, pure math"""
    
    def update_belief(
        self,
        prior: PriorBelief,
        evidence: Evidence,
        likelihood: Likelihood
    ) -> PriorBelief:
        """
        Bayes' rule: P(H|E) ∝ P(E|H) * P(H)
        
        Returns posterior belief distribution
        """
        posterior = {}
        
        for intent, prior_prob in prior.hypotheses.items():
            likelihood_score = likelihood.scores.get(intent, 0.01)
            posterior[intent] = likelihood_score * prior_prob
        
        return PriorBelief(hypotheses=posterior)  # Auto-normalizes
    
    def entropy(self, belief: PriorBelief) -> float:
        """
        Calculate entropy of belief distribution
        High entropy = uncertain, should ask clarifying question
        Low entropy = confident, should make recommendation
        """
        return -sum(
            p * math.log2(p) if p > 0 else 0
            for p in belief.hypotheses.values()
        )
    
    def expected_information_gain(
        self,
        current_belief: PriorBelief,
        possible_evidence: List[Evidence],
        likelihood_model: Likelihood
    ) -> Dict[str, float]:
        """
        Calculate expected information gain from each possible question
        Used for Active Inference - which action reduces uncertainty most?
        """
        current_entropy = self.entropy(current_belief)
        gains = {}
        
        for evidence in possible_evidence:
            # Simulate belief after observing this evidence
            posterior = self.update_belief(
                current_belief,
                evidence,
                likelihood_model
            )
            expected_entropy = self.entropy(posterior)
            gains[evidence.query_text] = current_entropy - expected_entropy
        
        return gains
```

**Key Point**: This is pure domain logic. No LLM calls, no database, no HTTP requests. Agents will use this, but it's testable in isolation.

#### **2. Agent Harness Layer**
Location: `application/agents/harness/`

```
application/agents/harness/
├── __init__.py
├── agent_loop.py         # Main agent loop (perception → action)
├── tool_executor.py      # Tool calling + observation
├── memory_manager.py     # Working memory + episodic + semantic
├── context_manager.py    # Context window + prompt caching
├── state_manager.py      # Replay/state persistence (RL optional later)
└── knowledge_capsule.py  # Agent-specific knowledge isolation
```

**Core Responsibilities**:
1. **Agent Loop**: Implement perception-action cycle
2. **Tool Execution**: Call tools, observe results, feed back to agent
3. **Memory Management**: Maintain run context + reusable summaries (belief objects optional later)
4. **Context Window**: Handle truncation, summarization, caching
5. **State Persistence**: Save/load run state for replay + audits (RL-style learning optional later)

**Example: Agent Loop (Inspired by OpenAI Codex Harness)**

> Note: the “Active Inference / Bayesian beliefs” loop below is a future-looking sketch.
> Phase 0–3 can implement a simpler tool/observation loop (perceive → call tool → log → respond),
> and add richer belief updates only after we have calibration data.
```python
# application/agents/harness/agent_loop.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum

class AgentState(Enum):
    """Agent execution states"""
    PERCEIVING = "perceiving"      # Observing environment
    REASONING = "reasoning"         # Inferring next action
    ACTING = "acting"              # Executing tool
    REFLECTING = "reflecting"      # Learning from outcome

@dataclass
class AgentObservation:
    """What the agent perceives"""
    type: str  # "user_query" | "tool_result" | "memory_retrieval"
    content: Any
    timestamp: float
    
@dataclass
class AgentAction:
    """What the agent decides to do"""
    type: str  # "call_tool" | "respond_to_user" | "ask_clarification"
    tool_name: Optional[str]
    arguments: Optional[Dict[str, Any]]
    reasoning: str  # Why this action minimizes surprise
    
@dataclass
class AgentBelief:
    """Agent's internal world model (Bayesian belief state)"""
    intent_distribution: Dict[str, float]  # P(intent | observations)
    product_scores: Dict[str, float]       # P(product fits | intent)
    uncertainty: float                      # Entropy of beliefs
    evidence: List[AgentObservation]       # Supporting observations

class AgentLoop:
    """
    Core agent harness implementing Active Inference loop
    
    Based on Free Energy Principle:
    - Agent maintains beliefs about hidden states (user intent)
    - Agent observes environment through tools
    - Agent acts to minimize surprise (expected free energy)
    """
    
    def __init__(
        self,
        agent_id: str,
        llm_client: Any,  # LLM interface
        tool_executor: Any,  # Tool calling interface
        memory_manager: Any,  # Memory management
        context_manager: Any,  # Context window management
        max_iterations: int = 10,
        surprise_threshold: float = 0.5
    ):
        self.agent_id = agent_id
        self.llm = llm_client
        self.tools = tool_executor
        self.memory = memory_manager
        self.context = context_manager
        self.max_iterations = max_iterations
        self.surprise_threshold = surprise_threshold
        
        self.state = AgentState.PERCEIVING
        self.beliefs: Optional[AgentBelief] = None
        self.iteration = 0
        
    async def run(
        self,
        initial_observation: AgentObservation,
        goal: str
    ) -> Dict[str, Any]:
        """
        Main agent loop - implements Active Inference
        
        Loop:
        1. Perceive: Gather observations
        2. Infer: Update beliefs (Bayesian update)
        3. Plan: Choose action that minimizes expected free energy
        4. Act: Execute action, observe result
        5. Learn: Update beliefs based on outcome
        6. Repeat until goal achieved or surprise minimized
        """
        
        # Initialize beliefs from memory + observation
        self.beliefs = await self._initialize_beliefs(initial_observation)
        
        conversation_history = []
        
        while self.iteration < self.max_iterations:
            self.iteration += 1
            
            # === PERCEPTION ===
            self.state = AgentState.PERCEIVING
            observations = await self._gather_observations(conversation_history)
            
            # === INFERENCE (Bayesian Update) ===
            self.state = AgentState.REASONING
            self.beliefs = await self._update_beliefs(
                self.beliefs,
                observations
            )
            
            # Check if we've minimized surprise enough
            if self.beliefs.uncertainty < self.surprise_threshold:
                # Confident enough to act
                break
            
            # === PLANNING (Minimize Expected Free Energy) ===
            action = await self._plan_action(self.beliefs, goal)
            
            # === ACTION ===
            self.state = AgentState.ACTING
            
            if action.type == "respond_to_user":
                # We're done
                break
            
            if action.type == "call_tool":
                # Execute tool and observe result
                tool_result = await self.tools.execute(
                    action.tool_name,
                    action.arguments
                )
                
                # Add to conversation history
                conversation_history.append({
                    "role": "assistant",
                    "content": f"Calling tool: {action.tool_name}",
                    "tool_call": action.tool_name,
                    "reasoning": action.reasoning
                })
                conversation_history.append({
                    "role": "tool",
                    "content": tool_result,
                    "tool_name": action.tool_name
                })
                
                # Create observation from tool result
                tool_observation = AgentObservation(
                    type="tool_result",
                    content=tool_result,
                    timestamp=time.time()
                )
                
            # === REFLECTION (Learn from Outcome) ===
            self.state = AgentState.REFLECTING
            await self._learn_from_outcome(action, tool_observation)
        
        # Generate final response
        final_response = await self._generate_response(
            self.beliefs,
            conversation_history
        )
        
        # Persist state for future episodes
        await self._save_episode(
            initial_observation,
            conversation_history,
            final_response,
            self.beliefs
        )
        
        return {
            "response": final_response,
            "beliefs": self.beliefs,
            "iterations": self.iteration,
            "conversation_history": conversation_history
        }
    
    async def _initialize_beliefs(
        self,
        observation: AgentObservation
    ) -> AgentBelief:
        """
        Initialize belief state from memory + observation
        
        This is the prior P(H) in Bayesian inference
        """
        # Retrieve relevant past episodes from memory
        past_context = await self.memory.retrieve_relevant_context(
            observation.content
        )
        
        # Start with uniform prior or use past patterns
        if past_context:
            intent_distribution = past_context.get("intent_patterns", {})
        else:
            # Uniform prior over common intents
            intent_distribution = {
                "research": 0.3,
                "compare": 0.2,
                "evaluate_fit": 0.2,
                "ready_to_purchase": 0.1,
                "seeking_deal": 0.1,
                "gift_shopping": 0.1
            }
        
        return AgentBelief(
            intent_distribution=intent_distribution,
            product_scores={},
            uncertainty=self._calculate_entropy(intent_distribution),
            evidence=[observation]
        )
    
    async def _update_beliefs(
        self,
        beliefs: AgentBelief,
        observations: List[AgentObservation]
    ) -> AgentBelief:
        """
        Bayesian belief update: P(H|E) ∝ P(E|H) * P(H)
        
        This is where Bayesian inference happens
        """
        # Use domain logic (no infrastructure)
        from domain.use_cases.infer_intent import BayesianIntentInference
        
        inference_engine = BayesianIntentInference()
        
        # Current belief is prior
        prior = PriorBelief(hypotheses=beliefs.intent_distribution)
        
        # Construct evidence from observations
        evidence = self._observations_to_evidence(observations)
        
        # Get likelihood P(E|H) from LLM or domain heuristics
        likelihood = await self._estimate_likelihood(evidence, prior)
        
        # Bayesian update
        posterior = inference_engine.update_belief(prior, evidence, likelihood)
        
        return AgentBelief(
            intent_distribution=posterior.hypotheses,
            product_scores=beliefs.product_scores,  # Will update separately
            uncertainty=inference_engine.entropy(posterior),
            evidence=beliefs.evidence + observations
        )
    
    async def _plan_action(
        self,
        beliefs: AgentBelief,
        goal: str
    ) -> AgentAction:
        """
        Choose action that minimizes expected free energy
        
        Expected Free Energy = Risk + Ambiguity
        - Risk: How far will outcome be from goal?
        - Ambiguity: How uncertain are we about outcome?
        
        Action types:
        - If uncertainty high: Ask clarifying question (reduce ambiguity)
        - If uncertainty low but no products scored: Call search tool (gather info)
        - If products scored: Return recommendation (achieve goal)
        """
        
        # High uncertainty = ask question to reduce ambiguity
        if beliefs.uncertainty > 0.7:
            return await self._plan_clarifying_question(beliefs)
        
        # Medium uncertainty but no product scores = need more data
        if beliefs.uncertainty > 0.3 and not beliefs.product_scores:
            return await self._plan_search_action(beliefs)
        
        # Low uncertainty and have products = recommend
        if beliefs.product_scores:
            return AgentAction(
                type="respond_to_user",
                tool_name=None,
                arguments=None,
                reasoning="Confident in intent and have scored products"
            )
        
        # Default: explore
        return await self._plan_exploratory_action(beliefs)
    
    async def _plan_clarifying_question(
        self,
        beliefs: AgentBelief
    ) -> AgentAction:
        """
        Use Active Inference to pick question that maximizes info gain
        """
        from domain.use_cases.infer_intent import BayesianIntentInference
        
        inference = BayesianIntentInference()
        
        # Generate candidate clarifying questions
        candidate_questions = [
            Evidence(query_text="What's your budget?", context_signals=[], constraints=[]),
            Evidence(query_text="When do you need it?", context_signals=[], constraints=[]),
            Evidence(query_text="Any specific brands you prefer?", context_signals=[], constraints=[])
        ]
        
        # Calculate expected information gain for each
        prior = PriorBelief(hypotheses=beliefs.intent_distribution)
        likelihood = Likelihood(scores=beliefs.intent_distribution)  # Simplified
        
        gains = inference.expected_information_gain(
            prior,
            candidate_questions,
            likelihood
        )
        
        # Pick question with highest gain
        best_question = max(gains, key=gains.get)
        
        return AgentAction(
            type="ask_clarification",
            tool_name="ask_user",
            arguments={"question": best_question},
            reasoning=f"This question reduces uncertainty most (gain: {gains[best_question]:.2f})"
        )
    
    def _calculate_entropy(self, distribution: Dict[str, float]) -> float:
        """Shannon entropy of probability distribution"""
        return -sum(
            p * math.log2(p) if p > 0 else 0
            for p in distribution.values()
        )
```

**Key Features of Agent Harness**:
1. **Bayesian Belief Tracking**: Maintains P(intent | observations) 
2. **Active Inference**: Chooses actions that minimize expected free energy
3. **Tool Loop**: Can call tools iteratively, learn from results
4. **Memory Integration**: Retrieves past context, stores new episodes
5. **Context Management**: Handles growing conversation history

#### **3. Agent Implementations**
Location: `application/agents/`

```
application/agents/
├── __init__.py
├── base_agent.py         # Base agent class using harness
├── layer1_agent.py       # Inference-based discovery agent
├── layer2_agent.py       # Protocol-based discovery agent
├── orchestrator_agent.py # Optional coordinator
├── harness/             # Agent harness components
└── tools/               # Agent-specific tools
    ├── layer1_tools.py  # Web scraping, semantic analysis
    └── layer2_tools.py  # API queries, feed validation
```

**Example: Layer 1 Agent**
```python
# application/agents/layer1_agent.py

from typing import Dict, Any
from application.agents.base_agent import BaseAgent
from application.agents.tools.layer1_tools import (
    infer_intent_tool,
    scrape_product_page_tool,
    extract_capabilities_tool,
    score_semantic_match_tool
)

class Layer1Agent(BaseAgent):
    """
    Agent responsible for inference-based product discovery
    
    Capabilities:
    - Infer user intent from natural language
    - Scrape and analyze web product pages
    - Extract capabilities from unstructured text
    - Score semantic alignment between intent and products
    
    State (now):
    - intent inference output + confidence/uncertainty
    - evidence observations + tool logs (replayable)
    - alignment scores + explanations
    
    Tools:
    - infer_intent: intent inference (current model-based; Bayesian optional later)
    - scrape_product_page: Fetch and parse product page
    - extract_capabilities: Transform specs → capabilities
    - score_semantic_match: Embedding-based alignment
    """
    
    def __init__(self, **kwargs):
        super().__init__(
            agent_id="layer1_agent",
            agent_type="inference_based_discovery",
            **kwargs
        )
        
        # Register Layer 1 specific tools
        self.register_tools([
            infer_intent_tool,
            scrape_product_page_tool,
            extract_capabilities_tool,
            score_semantic_match_tool
        ])
        
        # Agent-specific knowledge
        self.knowledge = {
            "discovery_mechanism": "web_crawling",
            "data_source": "unstructured_html",
            "inference_method": "semantic_similarity",
            "typical_latency": "hours_to_days"
        }
    
    async def solve_task(
        self,
        user_query: str,
        products: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Main task: Given user query, score products via inference
        
        Agent loop:
        1. Infer intent from query (Bayesian inference)
        2. For each product:
           a. Scrape page if URL provided
           b. Extract capabilities from text
           c. Score semantic match with intent
        3. Return ranked products with explanations
        """
        
        goal = f"Score products for query: {user_query}"
        
        initial_observation = AgentObservation(
            type="user_query",
            content=user_query,
            timestamp=time.time()
        )
        
        # Run agent loop (handles tool calling, belief updates)
        result = await self.agent_loop.run(
            initial_observation=initial_observation,
            goal=goal
        )
        
        return {
            "agent": "layer1",
            "mechanism": "inference_based",
            "scored_products": result.get("scored_products", []),
            "beliefs": result.get("beliefs"),
            "reasoning": result.get("reasoning")
        }
```

**Example: Layer 2 Agent**
```python
# application/agents/layer2_agent.py

from typing import Dict, Any
from application.agents.base_agent import BaseAgent
from application.agents.tools.layer2_tools import (
    query_acp_feed_tool,
    query_ucp_api_tool,
    validate_feed_schema_tool,
    score_structured_match_tool
)

class Layer2Agent(BaseAgent):
    """
    Agent responsible for protocol-based product discovery
    
    Capabilities:
    - Query ACP/UCP feeds with structured parameters
    - Validate feed schema compliance
    - Score products based on explicit attribute matches
    - Check real-time inventory and pricing
    
    World Model (Beliefs):
    - P(merchant has ACP/UCP integration | merchant_id)
    - P(product matches query | structured_attributes)
    - P(product available | inventory_api_response)
    
    Tools:
    - query_acp_feed: Call OpenAI's ACP endpoints
    - query_ucp_api: Call Google's UCP endpoints
    - validate_feed_schema: Check feed compliance
    - score_structured_match: Exact attribute matching
    """
    
    def __init__(self, **kwargs):
        super().__init__(
            agent_id="layer2_agent",
            agent_type="protocol_based_discovery",
            **kwargs
        )
        
        # Register Layer 2 specific tools
        self.register_tools([
            query_acp_feed_tool,
            query_ucp_api_tool,
            validate_feed_schema_tool,
            score_structured_match_tool
        ])
        
        # Agent-specific knowledge
        self.knowledge = {
            "discovery_mechanism": "api_queries",
            "data_source": "structured_feeds",
            "inference_method": "exact_matching",
            "typical_latency": "milliseconds"
        }
    
    async def solve_task(
        self,
        user_query: str,
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main task: Query protocol feeds with structured parameters
        
        Agent loop:
        1. Transform user intent into API query parameters
        2. Query available protocol feeds (ACP, UCP, Shopify)
        3. For each product:
           a. Validate schema compliance
           b. Score exact attribute matches
           c. Check real-time availability
        4. Return ranked products with explanations
        """
        
        goal = f"Query protocol feeds for: {intent['primary_goal']}"
        
        initial_observation = AgentObservation(
            type="intent_specification",
            content=intent,
            timestamp=time.time()
        )
        
        # Run agent loop
        result = await self.agent_loop.run(
            initial_observation=initial_observation,
            goal=goal
        )
        
        return {
            "agent": "layer2",
            "mechanism": "protocol_based",
            "scored_products": result.get("scored_products", []),
            "beliefs": result.get("beliefs"),
            "reasoning": result.get("reasoning")
        }
```

**Example: Orchestrator Agent**
```python
# application/agents/orchestrator_agent.py

from typing import Dict, Any, List
from application.agents.base_agent import BaseAgent

class OrchestratorAgent(BaseAgent):
    """
    Optional coordinator agent that:
    - Decides when to query Layer 1 vs Layer 2
    - Synthesizes results from both agents
    - Critiques outputs for consistency
    - Resolves conflicts between layers
    
    Decision Logic:
    - If merchant has protocol integration → Prefer Layer 2
    - If query is ambiguous → Start with Layer 1 (infer intent first)
    - If products found in both → Synthesize, check consistency
    - If results conflict → Explain differences to user
    """
    
    def __init__(
        self,
        layer1_agent: Layer1Agent,
        layer2_agent: Layer2Agent,
        **kwargs
    ):
        super().__init__(
            agent_id="orchestrator",
            agent_type="coordinator",
            **kwargs
        )
        
        self.layer1 = layer1_agent
        self.layer2 = layer2_agent
        
        # Register orchestration tools
        self.register_tools([
            self._query_layer1_tool(),
            self._query_layer2_tool(),
            self._synthesize_results_tool(),
            self._resolve_conflicts_tool()
        ])
    
    async def solve_task(
        self,
        user_query: str,
        products: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Coordinate Layer 1 and Layer 2 agents
        
        Strategy:
        1. Determine which layer(s) to query based on context
        2. Run agents in parallel or sequence
        3. Synthesize results
        4. Return unified recommendation with provenance
        """
        
        # Decide strategy
        strategy = await self._decide_strategy(user_query, products)
        
        results = {}
        
        if strategy.use_layer1:
            results["layer1"] = await self.layer1.solve_task(
                user_query=user_query,
                products=products
            )
        
        if strategy.use_layer2:
            # If Layer 1 ran first, use its intent inference
            intent = results.get("layer1", {}).get("beliefs", {}).get("intent")
            
            results["layer2"] = await self.layer2.solve_task(
                user_query=user_query,
                intent=intent or self._extract_intent(user_query)
            )
        
        # Synthesize
        final_result = await self._synthesize(results, strategy)
        
        return {
            "orchestrator": True,
            "strategy": strategy,
            "layer1_result": results.get("layer1"),
            "layer2_result": results.get("layer2"),
            "synthesized": final_result
        }
    
    async def _decide_strategy(
        self,
        user_query: str,
        products: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Decide which layers to query
        
        Heuristics:
        - If products have `protocol_integration: true` → Layer 2 first
        - If query is vague → Layer 1 first (infer intent)
        - If budget allows → Both in parallel
        """
        
        has_protocol = any(
            p.get("protocol_integration") for p in products
        )
        
        query_is_vague = await self._assess_query_clarity(user_query)
        
        return {
            "use_layer1": query_is_vague or not has_protocol,
            "use_layer2": has_protocol,
            "parallel": has_protocol and not query_is_vague,
            "reasoning": "..."
        }
```

#### **4. Infrastructure Layer**
Location: `infrastructure/`

```
infrastructure/
├── __init__.py
├── repositories/         # Concrete implementations
│   ├── product_repository.py   # SQLite + adapters
│   ├── memory_repository.py    # SQLite + vector store
│   ├── llm_repository.py       # Gemini, OpenRouter clients
│   └── evidence_repository.py  # Web scraping
│
├── adapters/            # External system adapters
│   ├── shopify_adapter.py
│   ├── merchant_center_adapter.py
│   ├── acp_adapter.py   # OpenAI ACP protocol
│   ├── ucp_adapter.py   # Google UCP protocol
│   └── vector_store_adapter.py
│
└── external/           # Third-party clients
    ├── gemini_client.py
    ├── openrouter_client.py
    └── web_scraper.py
```

**Example: Protocol Adapter (ACP)**
```python
# infrastructure/adapters/acp_adapter.py

from typing import Dict, Any, List
import httpx

class ACPAdapter:
    """
    Adapter for OpenAI's Agentic Commerce Protocol
    
    Implements:
    - Product feed queries
    - Checkout session creation
    - Order management
    """
    
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"}
        )
    
    async def query_products(
        self,
        query: str,
        filters: Dict[str, Any] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query merchant product feed
        
        Endpoint: GET /products
        Query params: query, filters (JSON), limit
        """
        
        params = {
            "query": query,
            "limit": limit
        }
        
        if filters:
            params["filters"] = json.dumps(filters)
        
        response = await self.client.get("/products", params=params)
        response.raise_for_status()
        
        data = response.json()
        
        return data.get("products", [])
    
    async def create_checkout_session(
        self,
        product_ids: List[str],
        customer_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create checkout session for selected products
        
        Endpoint: POST /checkout/create
        """
        
        payload = {
            "products": product_ids,
            "context": customer_context
        }
        
        response = await self.client.post("/checkout/create", json=payload)
        response.raise_for_status()
        
        return response.json()
```

---

## Agent Tool Specifications

### Layer 1 Agent Tools

```python
# application/agents/tools/layer1_tools.py

from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    function: callable

# Tool 1: Infer Intent
infer_intent_tool = Tool(
    name="infer_intent",
    description="Infer user's underlying intent from query and context using Bayesian inference",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "User's search query"},
            "context": {
                "type": "object",
                "description": "Additional context (history, preferences, constraints)"
            }
        },
        "required": ["query"]
    },
    function=async def infer_intent(query: str, context: Dict = None):
        """
        Uses domain/use_cases/infer_intent.py
        
        Returns:
        {
            "primary_goal": str,
            "underlying_needs": List[str],
            "constraints": List[str],
            "confidence": float
        }
        """
        from domain.use_cases.infer_intent import BayesianIntentInference
        # ... implementation
)

# Tool 2: Scrape Product Page
scrape_product_page_tool = Tool(
    name="scrape_product_page",
    description="Fetch and parse a product page from URL",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Product page URL"},
            "extract": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Fields to extract (title, price, description, specs)"
            }
        },
        "required": ["url"]
    },
    function=async def scrape_product_page(url: str, extract: List[str] = None):
        """
        Uses infrastructure/external/web_scraper.py
        
        Returns:
        {
            "title": str,
            "price": float,
            "description": str,
            "specs": Dict[str, str],
            "raw_html": str
        }
        """
        from infrastructure.external.web_scraper import WebScraper
        # ... implementation
)

# Tool 3: Extract Capabilities
extract_capabilities_tool = Tool(
    name="extract_capabilities",
    description="Transform product specs into human-centric capabilities and outcomes",
    parameters={
        "type": "object",
        "properties": {
            "product_data": {
                "type": "object",
                "description": "Product specs and description"
            }
        },
        "required": ["product_data"]
    },
    function=async def extract_capabilities(product_data: Dict):
        """
        Uses domain/use_cases/profile_product.py
        
        Returns:
        {
            "capabilities_enabled": List[str],
            "goals_served": List[str],
            "outcomes_expected": List[str],
            "context_fit": Dict[str, float]
        }
        """
        from domain.use_cases.profile_product import IntentionalityMapper
        # ... implementation
)

# Tool 4: Score Semantic Match
score_semantic_match_tool = Tool(
    name="score_semantic_match",
    description="Calculate semantic alignment between intent and product using embeddings",
    parameters={
        "type": "object",
        "properties": {
            "intent": {"type": "object", "description": "Inferred intent"},
            "product": {"type": "object", "description": "Product with capabilities"}
        },
        "required": ["intent", "product"]
    },
    function=async def score_semantic_match(intent: Dict, product: Dict):
        """
        Uses domain/use_cases/score_alignment.py
        
        Returns:
        {
            "score": float,
            "matched_needs": List[str],
            "gaps": List[str],
            "reasoning": str
        }
        """
        from domain.use_cases.score_alignment import AlignmentScorer
        # ... implementation
)
```

### Layer 2 Agent Tools

```python
# application/agents/tools/layer2_tools.py

# Tool 1: Query ACP Feed
query_acp_feed_tool = Tool(
    name="query_acp_feed",
    description="Query merchant product feed via OpenAI's ACP protocol",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "filters": {
                "type": "object",
                "description": "Structured filters (price, category, attributes)"
            },
            "limit": {"type": "integer", "description": "Max results"}
        },
        "required": ["query"]
    },
    function=async def query_acp_feed(
        query: str,
        filters: Dict = None,
        limit: int = 10
    ):
        """
        Uses infrastructure/adapters/acp_adapter.py
        
        Returns:
        {
            "products": List[Dict],
            "total": int,
            "filters_applied": Dict
        }
        """
        from infrastructure.adapters.acp_adapter import ACPAdapter
        # ... implementation
)

# Tool 2: Query UCP API
query_ucp_api_tool = Tool(
    name="query_ucp_api",
    description="Query merchant via Google's Universal Commerce Protocol",
    parameters={
        "type": "object",
        "properties": {
            "merchant_id": {"type": "string"},
            "query": {"type": "string"},
            "filters": {"type": "object"}
        },
        "required": ["merchant_id", "query"]
    },
    function=async def query_ucp_api(...):
        # Similar to ACP
)

# Tool 3: Validate Feed Schema
validate_feed_schema_tool = Tool(
    name="validate_feed_schema",
    description="Check if product feed complies with protocol schema",
    parameters={
        "type": "object",
        "properties": {
            "product_data": {"type": "object"},
            "protocol": {"type": "string", "enum": ["acp", "ucp"]}
        },
        "required": ["product_data", "protocol"]
    },
    function=async def validate_feed_schema(...):
        # Validation logic
)

# Tool 4: Score Structured Match
score_structured_match_tool = Tool(
    name="score_structured_match",
    description="Score product based on exact attribute matches with intent",
    parameters={
        "type": "object",
        "properties": {
            "intent_params": {"type": "object"},
            "product_attributes": {"type": "object"}
        },
        "required": ["intent_params", "product_attributes"]
    },
    function=async def score_structured_match(...):
        # Exact matching logic
)
```

---

## Memory Management

### Memory Types

```python
# application/agents/harness/memory_manager.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np

@dataclass
class WorkingMemory:
    """Short-term, session-scoped memory (7±2 items)"""
    items: List[Dict[str, Any]]
    max_size: int = 7
    
    def add(self, item: Dict[str, Any]):
        self.items.append(item)
        if len(self.items) > self.max_size:
            # Evict oldest
            self.items = self.items[-self.max_size:]
    
    def retrieve(self) -> List[Dict[str, Any]]:
        return self.items

@dataclass
class EpisodicMemory:
    """Long-term memory of specific interactions (episodes)"""
    episodes: List[Dict[str, Any]]
    
    def store_episode(
        self,
        agent_id: str,
        query: str,
        actions: List[Dict],
        outcome: Dict,
        timestamp: float
    ):
        episode = {
            "agent_id": agent_id,
            "query": query,
            "actions": actions,
            "outcome": outcome,
            "timestamp": timestamp
        }
        self.episodes.append(episode)
    
    def retrieve_similar_episodes(
        self,
        current_query: str,
        top_k: int = 5
    ) -> List[Dict]:
        """Retrieve episodes similar to current query (via embeddings)"""
        # ... similarity search

@dataclass
class SemanticMemory:
    """Long-term memory of general knowledge (patterns, rules)"""
    knowledge: Dict[str, Any]
    
    def store_pattern(self, key: str, value: Any):
        """Store learned pattern or rule"""
        self.knowledge[key] = value
    
    def retrieve_pattern(self, key: str) -> Optional[Any]:
        return self.knowledge.get(key)

class MemoryManager:
    """
    Manages all three memory types for an agent
    
    Inspired by human memory systems:
    - Working: Active, limited capacity (conversation context)
    - Episodic: Past experiences (previous simulations)
    - Semantic: General knowledge (learned patterns)
    """
    
    def __init__(self, agent_id: str, db_connection: Any):
        self.agent_id = agent_id
        self.db = db_connection
        
        self.working = WorkingMemory(items=[])
        self.episodic = EpisodicMemory(episodes=[])
        self.semantic = SemanticMemory(knowledge={})
        
        # Load long-term memories from DB
        self._load_from_db()
    
    async def _load_from_db(self):
        """Load episodic and semantic memory from persistent storage"""
        # Load past episodes
        episodes = await self.db.query(
            "SELECT * FROM episodes WHERE agent_id = ? ORDER BY timestamp DESC LIMIT 100",
            (self.agent_id,)
        )
        self.episodic.episodes = episodes
        
        # Load semantic patterns
        patterns = await self.db.query(
            "SELECT * FROM semantic_memory WHERE agent_id = ?",
            (self.agent_id,)
        )
        for row in patterns:
            self.semantic.store_pattern(row["key"], row["value"])
    
    async def persist_episode(
        self,
        query: str,
        actions: List[Dict],
        outcome: Dict
    ):
        """Save episode to both in-memory and persistent storage"""
        import time
        
        timestamp = time.time()
        
        # In-memory
        self.episodic.store_episode(
            self.agent_id,
            query,
            actions,
            outcome,
            timestamp
        )
        
        # Persistent
        await self.db.execute(
            """
            INSERT INTO episodes (agent_id, query, actions, outcome, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (self.agent_id, query, json.dumps(actions), json.dumps(outcome), timestamp)
        )
    
    async def retrieve_relevant_context(
        self,
        current_query: str
    ) -> Dict[str, Any]:
        """
        Retrieve relevant memories for current query
        
        Returns context combining:
        - Similar past episodes
        - Relevant semantic patterns
        - Current working memory
        """
        
        # Get similar episodes
        similar_episodes = self.episodic.retrieve_similar_episodes(
            current_query,
            top_k=3
        )
        
        # Get relevant patterns
        # (In real implementation, use semantic search)
        relevant_patterns = {}
        
        return {
            "working_memory": self.working.retrieve(),
            "past_episodes": similar_episodes,
            "patterns": relevant_patterns
        }
```

---

## Context Window Management

```python
# application/agents/harness/context_manager.py

from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class ContextWindow:
    """
    Manages conversation history within token limits
    
    Strategies:
    - Prompt caching (reuse system prompt, recent history)
    - Truncation (drop oldest messages when over limit)
    - Summarization (compress old messages)
    """
    
    max_tokens: int
    messages: List[Dict[str, Any]]
    system_prompt: str
    
    def __post_init__(self):
        self.cached_prefix_length = 0
    
    def add_message(self, role: str, content: str):
        """Add message to context"""
        self.messages.append({"role": role, "content": content})
        
        # Check if over limit
        if self._estimate_tokens() > self.max_tokens:
            self._compact()
    
    def _estimate_tokens(self) -> int:
        """Estimate token count (rough approximation)"""
        # System prompt
        tokens = len(self.system_prompt) // 4
        
        # Messages
        for msg in self.messages:
            tokens += len(msg["content"]) // 4
        
        return tokens
    
    def _compact(self):
        """
        Reduce context size when over limit
        
        Strategy:
        1. Keep system prompt (cached)
        2. Keep last N messages (recent context)
        3. Summarize or drop middle messages
        """
        
        # Always keep last 5 messages
        recent = self.messages[-5:]
        
        # If still over limit, summarize older messages
        if self._estimate_tokens() > self.max_tokens:
            older = self.messages[:-5]
            summary = self._summarize_messages(older)
            
            # Replace older messages with summary
            self.messages = [
                {"role": "system", "content": f"Previous conversation summary: {summary}"}
            ] + recent
    
    def _summarize_messages(self, messages: List[Dict]) -> str:
        """Compress messages into summary (can use LLM)"""
        # Simple implementation: just concatenate
        return " | ".join(msg["content"][:100] for msg in messages)
    
    def get_messages_for_llm(self) -> List[Dict[str, Any]]:
        """
        Return messages formatted for LLM API call
        
        Includes cache markers for prompt caching
        """
        
        messages = [
            {"role": "system", "content": self.system_prompt}
        ] + self.messages
        
        # Mark cacheable prefix (system prompt + first few messages)
        if len(messages) > 3:
            # First 3 messages are cacheable
            messages[2]["cache_control"] = {"type": "ephemeral"}
        
        return messages
```

---

## State Persistence (RL Environment)

```python
# application/agents/harness/state_manager.py

from dataclasses import dataclass
from typing import Dict, Any, Optional
import json

@dataclass
class EnvironmentState:
    """
    Complete world state at a given time
    
    This is like gym.Env.state in RL - captures everything
    needed to resume from this point
    """
    
    # Agent state
    agent_id: str
    beliefs: Dict[str, Any]  # Current belief distribution
    working_memory: List[Dict]
    
    # Task state
    user_query: str
    products_evaluated: List[str]
    current_iteration: int
    
    # Observation history
    observations: List[Dict]
    actions: List[Dict]
    
    # Metadata
    timestamp: float
    session_id: str

class StateManager:
    """
    Manages state persistence for RL-style learning
    
    Analogous to gym.Env but for agent decision-making:
    - Save state at each step
    - Load past states for replay
    - Enable "rewind" for what-if analysis
    """
    
    def __init__(self, db_connection: Any):
        self.db = db_connection
    
    async def save_state(
        self,
        state: EnvironmentState
    ) -> str:
        """
        Persist state to database
        
        Returns: state_id for later retrieval
        """
        
        state_id = f"{state.session_id}_{state.current_iteration}"
        
        await self.db.execute(
            """
            INSERT INTO agent_states (
                state_id, agent_id, session_id, iteration,
                beliefs, working_memory, observations, actions,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state_id,
                state.agent_id,
                state.session_id,
                state.current_iteration,
                json.dumps(state.beliefs),
                json.dumps(state.working_memory),
                json.dumps(state.observations),
                json.dumps(state.actions),
                state.timestamp
            )
        )
        
        return state_id
    
    async def load_state(
        self,
        state_id: str
    ) -> Optional[EnvironmentState]:
        """Load state from database"""
        
        row = await self.db.query_one(
            "SELECT * FROM agent_states WHERE state_id = ?",
            (state_id,)
        )
        
        if not row:
            return None
        
        return EnvironmentState(
            agent_id=row["agent_id"],
            beliefs=json.loads(row["beliefs"]),
            working_memory=json.loads(row["working_memory"]),
            user_query="",  # Not stored, reconstruct if needed
            products_evaluated=[],
            current_iteration=row["iteration"],
            observations=json.loads(row["observations"]),
            actions=json.loads(row["actions"]),
            timestamp=row["timestamp"],
            session_id=row["session_id"]
        )
    
    async def get_trajectory(
        self,
        session_id: str
    ) -> List[EnvironmentState]:
        """
        Get full state trajectory for a session
        
        Useful for:
        - Analyzing agent behavior over time
        - Learning from successful episodes
        - Debugging failed episodes
        """
        
        rows = await self.db.query(
            """
            SELECT * FROM agent_states
            WHERE session_id = ?
            ORDER BY iteration ASC
            """,
            (session_id,)
        )
        
        return [self.load_state(row["state_id"]) for row in rows]
```

---

## API Integration

### Updated API Endpoints

```python
# api/routes/agents.py

from fastapi import APIRouter, Depends
from typing import Dict, Any

router = APIRouter(prefix="/agents", tags=["agents"])

@router.post("/query")
async def query_agents(
    query: str,
    products: List[Dict[str, Any]],
    client_id: str,
    use_layer1: bool = True,
    use_layer2: bool = True,
    use_orchestrator: bool = False
):
    """
    Query agentic system for product recommendations
    
    Parameters:
    - query: User's natural language query
    - products: List of products to evaluate
    - use_layer1: Enable inference-based agent
    - use_layer2: Enable protocol-based agent
    - use_orchestrator: Use orchestrator to coordinate
    
    Returns:
    {
        "layer1_result": {...},  # If enabled
        "layer2_result": {...},  # If enabled
        "orchestrated_result": {...},  # If orchestrator used
        "final_recommendation": [...],
        "reasoning": "..."
    }
    """
    
    from application.agents.layer1_agent import Layer1Agent
    from application.agents.layer2_agent import Layer2Agent
    from application.agents.orchestrator_agent import OrchestratorAgent
    
    results = {}
    
    # Initialize agents
    if use_layer1:
        agent1 = Layer1Agent()
        results["layer1"] = await agent1.solve_task(query, products)
    
    if use_layer2:
        agent2 = Layer2Agent()
        intent = results.get("layer1", {}).get("beliefs", {}).get("intent")
        results["layer2"] = await agent2.solve_task(query, intent or {})
    
    if use_orchestrator and use_layer1 and use_layer2:
        orchestrator = OrchestratorAgent(agent1, agent2)
        results["orchestrated"] = await orchestrator.solve_task(query, products)
    
    return results

@router.get("/agent/{agent_id}/memory")
async def get_agent_memory(agent_id: str):
    """Retrieve agent's memory state for inspection"""
    # ... implementation

@router.post("/agent/{agent_id}/reset")
async def reset_agent_memory(agent_id: str):
    """Reset agent's memory (for testing)"""
    # ... implementation
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Deliverables**:
- [ ] Clean Architecture refactor
  - [ ] Create `domain/` layer with pure business logic
  - [ ] Move modules to domain use cases
  - [ ] Create abstract repository interfaces
  - [ ] Implement concrete repositories in `infrastructure/`

- [ ] Agent Harness Core
  - [ ] Implement `agent_loop.py` with Bayesian belief tracking
  - [ ] Implement `tool_executor.py`
  - [ ] Implement `memory_manager.py` (working, episodic, semantic)
  - [ ] Implement `context_manager.py` with prompt caching

- [ ] Database Schema
  - [ ] Add `agent_states` table
  - [ ] Add `episodes` table (enhanced with agent_id, beliefs)
  - [ ] Add `agent_tools` table
  - [ ] Migration scripts

**Success Criteria**:
- Domain logic testable without infrastructure
- Agent loop can run with mock tools
- Memory persists across sessions

### Phase 2: Layer 1 Agent (Weeks 3-4)

**Deliverables**:
- [ ] Layer 1 Agent Implementation
  - [ ] `layer1_agent.py` using harness
  - [ ] Layer 1 tools (infer_intent, scrape_page, extract_capabilities, score_semantic)
  - [ ] Integration with existing modules via domain layer

- [ ] Testing
  - [ ] Unit tests for each tool
  - [ ] Integration test: full Layer 1 query
  - [ ] Comparison: old monolithic vs new agentic (should match)

**Success Criteria**:
- Layer 1 agent matches current inference-based flow
- Tool calls logged in agent_states
- Belief evolution visible in database

### Phase 3: Layer 2 Agent (Weeks 5-6)

**Deliverables**:
- [ ] Layer 2 Agent Implementation
  - [ ] `layer2_agent.py` using harness
  - [ ] Layer 2 tools (query_acp, query_ucp, validate_schema, score_structured)
  - [ ] ACP/UCP adapter implementations

- [ ] Protocol Integration
  - [ ] Mock ACP endpoint for testing
  - [ ] Mock UCP endpoint for testing
  - [ ] Real integration with Shopify Agentic Storefronts (if available)

**Success Criteria**:
- Layer 2 agent can query protocol feeds
- Structured matching works correctly
- Real-time inventory checks functional

### Phase 4: Orchestrator + Integration (Weeks 7-8)

**Deliverables**:
- [ ] Orchestrator Agent
  - [ ] `orchestrator_agent.py`
  - [ ] Decision logic for layer selection
  - [ ] Result synthesis
  - [ ] Conflict resolution

- [ ] API Updates
  - [ ] `/agents/query` endpoint
  - [ ] Agent memory inspection endpoints
  - [ ] State persistence endpoints

- [ ] UI Updates
  - [ ] Agent selection controls
  - [ ] Belief visualization
  - [ ] Tool call logs
  - [ ] Layer comparison view

**Success Criteria**:
- Orchestrator intelligently routes queries
- Results from both layers synthesized correctly
- UI shows agent reasoning process

### Phase 5: Learning & Optimization (Weeks 9-10)

**Deliverables**:
- [ ] Meta-Learning
  - [ ] Episode replay for pattern extraction
  - [ ] Learned patterns stored in semantic memory
  - [ ] Intent clustering from episodes

- [ ] Active Inference Enhancements
  - [ ] Information gain calculation for clarifying questions
  - [ ] Expected free energy for action selection
  - [ ] Surprise-based learning signals

- [ ] Performance Optimization
  - [ ] Prompt caching implementation
  - [ ] Parallel tool execution
  - [ ] Response streaming

**Success Criteria**:
- Agent learns from past episodes (measurable improvement)
- Clarifying questions are information-maximizing
- Response latency <2s for cached scenarios

---

## Migration Strategy

### Step 1: Parallel Implementation
- Build new agentic architecture **alongside** existing monolithic code
- No disruption to current functionality
- Gradual migration of modules to domain layer

### Step 2: Feature Parity
- Ensure new agents produce same results as old modules
- A/B testing: route some requests to agents, some to old code
- Compare outputs, measure latency

### Step 3: Gradual Cutover
- Start with Layer 1 agent (most mature)
- Then Layer 2 agent
- Finally orchestrator
- Old code can stay as fallback

### Step 4: Deprecation
- Once agents proven stable (95%+ uptime, <5% error rate)
- Deprecate old monolithic flow
- Remove legacy code

---

## Testing Strategy

### Unit Tests
- Domain logic: Pure functions, easy to test
- Agent tools: Mock LLM responses
- Memory operations: In-memory database

### Integration Tests
- Full agent loops with real tools
- Multi-turn conversations
- State persistence and replay

### End-to-End Tests
- API → Agents → Database → Response
- Simulate production scenarios
- Load testing (concurrent agent queries)

---

## Success Metrics

### Technical Metrics
- **Agent loop latency**: <2s for cached, <5s for cold
- **Memory hit rate**: >80% for episodic retrieval
- **Tool success rate**: >95% (tools execute without error)
- **Belief convergence**: <5 iterations to confident recommendation
- **Context window usage**: <70% to avoid truncation

### Business Metrics
- **Prediction accuracy**: Agent recommendations match real LLM outcomes >80%
- **Discovery lift**: Products optimized by agents show +40% recommendation rate
- **User satisfaction**: >4/5 rating on agent explanations

---

## Conclusion

This transformation converts your current monolithic module architecture into a sophisticated multi-agent system grounded in:

1. **Clean Architecture**: Domain logic pure, infrastructure pluggable
2. **Bayesian Inference**: Agents maintain probabilistic beliefs, update via Bayes' rule
3. **Active Inference**: Actions chosen to minimize expected free energy
4. **Agent Harness**: Memory, tools, context, state all managed systematically
5. **Reinforcement Learning**: State persistence enables learning from episodes

**The result**: A modular, scalable, theoretically grounded agentic platform that can:
- Handle both inference-based (Layer 1) and protocol-based (Layer 2) discovery
- Learn from outcomes and improve over time
- Explain its reasoning transparently
- Scale to thousands of concurrent agent queries

This is the architecture for the next decade of AI-driven product discovery.
