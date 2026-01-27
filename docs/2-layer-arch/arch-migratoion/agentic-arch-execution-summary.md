# Agentic Architecture: Executive Summary & Quick-Start Guide

> Reader guide:
> - **Actionable now (hackathon + near-term):** “Key Architectural Decisions”, “Implementation Roadmap”, “Testing Strategy”, “Migration Strategy”.
> - **Future experiments (do not implement yet):** anything explicitly labeled “Future Experiment” or “Appendix”.

## TL;DR: What We're Building

Transform your current **monolithic module architecture** into a **layered, agentic system** where:

```
┌──────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                         │
│            (Optional - coordinates Layer 1 & 2)               │
└──────────────────────────────────────────────────────────────┘
                           │
               ┌───────────┴───────────┐
               │                       │
               ▼                       ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│   LAYER 1 AGENT         │  │   LAYER 2 AGENT         │
│ (Inference Discovery)   │  │ (Protocol Discovery)    │
│                         │  │                         │
│ Tools:                  │  │ Tools:                  │
│ - infer_intent          │  │ - query_acp_feed        │
│ - scrape_page           │  │ - query_ucp_api         │
│ - extract_capabilities  │  │ - validate_schema       │
│ - score_semantic_match  │  │ - score_structured_match│
│                         │  │                         │
│ State (now):            │  │ State (now):            │
│ - confidence + evidence │  │ - schema validity + fit │
│ - replayable tool logs  │  │ - replayable tool logs  │
└─────────────────────────┘  └─────────────────────────┘
               │                       │
               └───────────┬───────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   MINIMAL AGENT HARNESS                       │
│  - Tool execution + observation logging                       │
│  - Context packaging + token budget policies                  │
│  - Memory adapter (working, episodic, semantic)               │
│  - Replay metadata (model/prompt/scoring versions)            │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              DOMAIN LAYER (Clean Architecture)                │
│  Pure business logic - no infrastructure dependencies         │
│  - Bayesian intent inference                                  │
│  - Intentionality mapping                                     │
│  - Alignment scoring                                          │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                         │
│  - LLM clients (Gemini, OpenRouter)                           │
│  - Database (SQLite)                                          │
│  - External APIs (Shopify, ACP, UCP)                          │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Architectural Decisions

### 0. **What “Agentic” Means Here (Measurable)**

We only adopt “agentic” components if they improve:
- Prediction accuracy (simulation vs verified outcomes)
- Time-to-insight (less manual iteration)
- Optimization quality (better copy + clearer “why you lost”)

Full RL training and “Bayesian beliefs everywhere” are **future experiments** once enough calibration data exists.
In the near-term, we model “belief/state” as: **inputs → tools used → observations → outputs**, plus a **confidence/uncertainty** estimate and a full replay record.

### 1. **Three-Agent System (Recommended)**

**Layer 1 Agent**: Handles inference-based discovery
- Crawls web pages, extracts unstructured data
- Infers product capabilities from text
- Scores semantic alignment via embeddings

**Layer 2 Agent**: Handles protocol-based discovery  
- Queries ACP/UCP structured feeds
- Validates schema compliance
- Scores exact attribute matches

**Orchestrator Agent**: Coordinates both layers
- Decides which layer(s) to query based on context
- Synthesizes results from both agents
- Resolves conflicts between layers

**Alternative**: Skip orchestrator, run both agents in parallel and merge results programmatically.

### 2. **Clean Architecture Layers**

```
┌─────────────────────────────────────────────┐
│         DOMAIN (Core Business Logic)        │
│  • Intent inference (Bayesian)              │
│  • Intentionality mapping (specs → caps)    │
│  • Alignment scoring                        │
│  • Pure functions, no infrastructure        │
└─────────────────────────────────────────────┘
                    ▲
                    │ depends on
┌─────────────────────────────────────────────┐
│      APPLICATION (Agent Harness + Agents)   │
│  • Agent loop (perception-action)           │
│  • Tool execution                           │
│  • Memory management                        │
│  • Context window management                │
└─────────────────────────────────────────────┘
                    ▲
                    │ depends on
┌─────────────────────────────────────────────┐
│      INFRASTRUCTURE (External Systems)      │
│  • LLM clients                              │
│  • Database repositories                    │
│  • External APIs (Shopify, ACP, UCP)        │
└─────────────────────────────────────────────┘
```

**Critical Rule**: Domain never depends on Infrastructure. Agents and Infrastructure depend on Domain.

### 3. **Agent Harness Components**

Based on OpenAI Codex harness design:

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| **Agent Loop** | Perception → Inference → Action cycle | `llm/agents/harness/agent_loop.py` |
| **Tool Executor** | Execute tools, observe results | `llm/agents/harness/tool_executor.py` *(or `tool_registry.py` for LLM tool schemas)* |
| **Memory Manager** | Working, episodic, semantic memory | `llm/agents/harness/memory_manager.py` *(initially wraps existing `SessionManager`)* |
| **Context Manager** | Context window + prompt caching | `llm/agents/harness/context_manager.py` |
| **Replay Logger** | Run inputs/outputs + versioning for reproducibility | `llm/agents/harness/replay_logger.py` |
| **Knowledge Capsule** | Agent-specific knowledge isolation | `llm/agents/harness/knowledge_capsule.py` |

### 4. **Bayesian Inference Integration (Future Experiment)**

Agents can maintain **probabilistic beliefs** about world state once we have enough verified outcomes to calibrate.
This is explicitly not required for Phase 0–3; keep it as an experiment track.

```python
@dataclass
class AgentBelief:
    """Agent's internal world model"""
    intent_distribution: Dict[str, float]  # P(intent | observations)
    product_scores: Dict[str, float]       # P(product fits | intent)
    uncertainty: float                      # Entropy of beliefs
    evidence: List[AgentObservation]       # Supporting observations
```

**Belief updating via Bayes' rule**:
```python
# P(H|E) ∝ P(E|H) * P(H)
posterior = likelihood * prior
```

**Action selection via Active Inference**:
- If uncertainty high → Ask clarifying question (reduce ambiguity)
- If uncertainty low but no products → Call search tool (gather info)
- If products scored → Return recommendation (achieve goal)

### 5. **Reinforcement Learning Environment (Future Experiment)**

Agents can persist state at each step like `gym.Env` **later** if we decide to explore true RL-style training. For now we only require replay logging + outcome tracking.

```python
@dataclass
class EnvironmentState:
    agent_id: str
    beliefs: Dict[str, Any]        # Current belief distribution
    working_memory: List[Dict]     # Active context
    observations: List[Dict]       # What agent has seen
    actions: List[Dict]            # What agent has done
    current_iteration: int
    timestamp: float
```

**Learning loop**:
1. Agent takes action
2. Observes outcome
3. Updates beliefs (Bayesian update)
4. Stores episode in memory
5. Learns patterns across episodes (meta-learning)

---

## Directory Structure Transformation

### Current Structure
```
llm/
  - agents/ (empty)
  - clients/
  - gateway.py
  - orchestrator.py
  - prompts.py
  - tools.py

modules/
  - intent/
  - intentionality/
  - alignment/
  - simulation/
  - memory/
  - commerce/
  - conversation/
  - evidence/
```

### Target Structure
```
domain/                      # NEW - Pure business logic
  - entities/
  - use_cases/
    - infer_intent.py        # Bayesian inference (pure functions)
    - profile_product.py     # Intentionality mapping
    - score_alignment.py     # Alignment calculation
  - repositories/            # Abstract interfaces only
  - value_objects/

llm/agents/                  # ENHANCED
  - harness/                 # NEW - Agent management
    - agent_loop.py
    - tool_executor.py
    - memory_manager.py
    - context_manager.py
    - state_manager.py
  - layer1_agent.py          # NEW
  - layer2_agent.py          # NEW
  - orchestrator_agent.py    # NEW
  - base_agent.py            # NEW
  - tools/                   # NEW
    - layer1_tools.py
    - layer2_tools.py

infrastructure/              # NEW - Concrete implementations
  - repositories/
  - adapters/
    - shopify_adapter.py
    - acp_adapter.py
    - ucp_adapter.py
  - external/
    - gemini_client.py
    - openrouter_client.py

modules/                     # REFACTORED - Becomes thinner
  - (Most logic moves to domain/ or llm/agents/)
```

---

## Implementation Roadmap (Incremental / Strangler)

### Phase 0: Guardrails (1–2 days)
- [ ] Define boundaries: `domain/`, `application/`, `infrastructure/`, `llm/agents/`
- [ ] Add replay metadata to every run (provider/model, prompt version, scoring version)
- [ ] Require deterministic fallbacks + replay runner for debugging

### Phase 1: Clean Architecture Skeleton (2–5 days)
- [ ] Create `domain/` for pure entities + pure functions (no FastAPI, no sqlite, no LLM client)
- [ ] Create `application/` services that the API calls (Simulation/Evidence/Admin/Verification)
- [ ] Keep `modules/*` as compatibility shims that delegate to domain/application

### Phase 2: Minimal Harness (2–4 days)
- [ ] Implement tool registry + executor (tool calls become logged observations)
- [ ] Implement context builder (token budget policies, prompt caching)
- [ ] Implement replay logger (inputs/outputs/versions/timing for every run)

### Phase 3: Layer 1 + Layer 2 Agents (3–7 days)
- [ ] Layer 1 agent wraps the existing evidence/web pipeline via tools
- [ ] Layer 2 agent wraps protocol simulation (ACP/UCP mocks) via tools
- [ ] Application orchestrator routes between layers (rule-based/confidence-based; no “mystical coordinator” required)

### Phase 4: Verification + Calibration (ongoing)
- [ ] Integrate one real verification surface
- [ ] Track predicted vs actual winners and accuracy over time
- [ ] Adjust scoring weights + confidence thresholds based on calibration data

### Phase 5: Future Experiments (after enough data)
- [ ] RL-style policy learning
- [ ] Bayesian belief objects across steps as first-class state
- [ ] Active inference action selection based on information gain

---

## Quick-Start: Building Your First Agent (Practical / Minimal)

This quick-start is intentionally minimal:
- Wrap existing application services as tools first.
- Add richer “belief objects” only after we have verified outcomes to calibrate against.

### Step 1: Define Domain Logic (Pure Function)

Note: The Bayesian belief objects below illustrate the *kind* of pure logic that can live in `domain/`, but we do not require “belief objects everywhere” in early phases. Start with simple scoring + calibration metrics first, then iterate.

```python
# domain/use_cases/infer_intent.py

from dataclasses import dataclass
from typing import Dict, List

@dataclass
class PriorBelief:
    hypotheses: Dict[str, float]  # intent → probability

@dataclass
class Evidence:
    query_text: str
    context_signals: List[str]
    constraints: List[str]

class BayesianIntentInference:
    """Pure Bayesian belief updating - no LLM calls"""
    
    def update_belief(
        self,
        prior: PriorBelief,
        evidence: Evidence,
        likelihood: Dict[str, float]
    ) -> PriorBelief:
        """Bayes' rule: P(H|E) ∝ P(E|H) * P(H)"""
        posterior = {}
        for intent, prior_prob in prior.hypotheses.items():
            likelihood_score = likelihood.get(intent, 0.01)
            posterior[intent] = likelihood_score * prior_prob
        
        # Normalize
        total = sum(posterior.values())
        if total > 0:
            posterior = {k: v/total for k, v in posterior.items()}
        
        return PriorBelief(hypotheses=posterior)
    
    def entropy(self, belief: PriorBelief) -> float:
        """Calculate uncertainty (high = should ask question)"""
        import math
        return -sum(
            p * math.log2(p) if p > 0 else 0
            for p in belief.hypotheses.values()
        )
```

### Step 2: Define Agent Tools

```python
# llm/agents/tools/layer1_tools.py

from dataclasses import dataclass
from typing import Dict, Any, Callable

@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable

async def infer_intent(query: str, context: Dict = None):
    """Infer user intent using domain logic"""
    from domain.use_cases.infer_intent import BayesianIntentInference
    
    # Initialize prior belief
    prior = PriorBelief(hypotheses={
        "research": 0.3,
        "compare": 0.2,
        "evaluate_fit": 0.2,
        "ready_to_purchase": 0.15,
        "gift_shopping": 0.15
    })
    
    # Construct evidence
    evidence = Evidence(
        query_text=query,
        context_signals=context.get("signals", []) if context else [],
        constraints=context.get("constraints", []) if context else []
    )
    
    # Get likelihood (can use LLM here)
    likelihood = await estimate_likelihood(evidence, prior)
    
    # Bayesian update
    inference = BayesianIntentInference()
    posterior = inference.update_belief(prior, evidence, likelihood)
    
    return {
        "intent_distribution": posterior.hypotheses,
        "uncertainty": inference.entropy(posterior),
        "primary_intent": max(posterior.hypotheses, key=posterior.hypotheses.get)
    }

# Tool definition
infer_intent_tool = Tool(
    name="infer_intent",
    description="Infer user's underlying intent from query and context",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "context": {"type": "object"}
        },
        "required": ["query"]
    },
    function=infer_intent
)
```

### Step 3: Implement Agent Loop

```python
# llm/agents/harness/agent_loop.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum

class AgentState(Enum):
    PERCEIVING = "perceiving"
    REASONING = "reasoning"
    ACTING = "acting"
    REFLECTING = "reflecting"

@dataclass
class AgentBelief:
    intent_distribution: Dict[str, float]
    product_scores: Dict[str, float]
    uncertainty: float
    evidence: List[Any]

class AgentLoop:
    """
    Core agent harness implementing a tool/observation loop (minimal version).

    Phase 0–3 loop:
    1) Perceive: gather observations (tool results, cached context)
    2) Decide: pick next tool (or return response) using rules/LLM reasoning
    3) Act: execute tool
    4) Log: persist observations + timings for replay

    Active inference / Bayesian belief updates are future experiments once we can calibrate.
    """
    
    def __init__(
        self,
        agent_id: str,
        llm_client: Any,
        tool_executor: Any,
        memory_manager: Any,
        max_iterations: int = 10,
        surprise_threshold: float = 0.5
    ):
        self.agent_id = agent_id
        self.llm = llm_client
        self.tools = tool_executor
        self.memory = memory_manager
        self.max_iterations = max_iterations
        self.surprise_threshold = surprise_threshold
        
        self.state = AgentState.PERCEIVING
        self.beliefs: Optional[AgentBelief] = None
        self.iteration = 0
    
    async def run(
        self,
        initial_observation: Dict,
        goal: str
    ) -> Dict[str, Any]:
        """Main agent loop"""
        
        # Initialize beliefs
        self.beliefs = await self._initialize_beliefs(initial_observation)
        
        conversation_history = []
        
        while self.iteration < self.max_iterations:
            self.iteration += 1
            
            # PERCEPTION
            self.state = AgentState.PERCEIVING
            observations = await self._gather_observations(conversation_history)
            
            # INFERENCE (Bayesian Update)
            self.state = AgentState.REASONING
            self.beliefs = await self._update_beliefs(self.beliefs, observations)
            
            # Check if uncertainty is low enough
            if self.beliefs.uncertainty < self.surprise_threshold:
                break
            
            # PLANNING (Minimize Expected Free Energy)
            action = await self._plan_action(self.beliefs, goal)
            
            # ACTION
            self.state = AgentState.ACTING
            if action["type"] == "respond_to_user":
                break
            
            if action["type"] == "call_tool":
                tool_result = await self.tools.execute(
                    action["tool_name"],
                    action["arguments"]
                )
                conversation_history.append({
                    "role": "tool",
                    "content": tool_result
                })
            
            # REFLECTION
            self.state = AgentState.REFLECTING
            await self._learn_from_outcome(action, tool_result)
        
        # Generate final response
        final_response = await self._generate_response(
            self.beliefs,
            conversation_history
        )
        
        # Persist state
        await self._save_episode(
            initial_observation,
            conversation_history,
            final_response,
            self.beliefs
        )
        
        return {
            "response": final_response,
            "beliefs": self.beliefs,
            "iterations": self.iteration
        }
```

### Step 4: Create Agent

```python
# llm/agents/layer1_agent.py

from llm.agents.base_agent import BaseAgent
from llm.agents.tools.layer1_tools import (
    infer_intent_tool,
    scrape_product_page_tool,
    extract_capabilities_tool,
    score_semantic_match_tool
)

class Layer1Agent(BaseAgent):
    """Agent for inference-based discovery"""
    
    def __init__(self, **kwargs):
        super().__init__(
            agent_id="layer1_agent",
            agent_type="inference_based_discovery",
            **kwargs
        )
        
        # Register tools
        self.register_tools([
            infer_intent_tool,
            scrape_product_page_tool,
            extract_capabilities_tool,
            score_semantic_match_tool
        ])
    
    async def solve_task(
        self,
        user_query: str,
        products: List[Dict]
    ) -> Dict[str, Any]:
        """Main task: Score products via inference"""
        
        goal = f"Score products for query: {user_query}"
        
        result = await self.agent_loop.run(
            initial_observation={"query": user_query},
            goal=goal
        )
        
        return {
            "agent": "layer1",
            "mechanism": "inference_based",
            "scored_products": result.get("scored_products", []),
            "beliefs": result.get("beliefs")
        }
```

### Step 5: Use Agent via API

```python
# api/routes/agents.py

from fastapi import APIRouter
from llm.agents.layer1_agent import Layer1Agent
from llm.agents.layer2_agent import Layer2Agent

router = APIRouter(prefix="/agents")

@router.post("/query")
async def query_agents(
    query: str,
    products: List[Dict],
    client_id: str,
    use_layer1: bool = True,
    use_layer2: bool = True
):
    """Query agentic system"""
    
    results = {}
    
    if use_layer1:
        agent1 = Layer1Agent()
        results["layer1"] = await agent1.solve_task(query, products)
    
    if use_layer2:
        agent2 = Layer2Agent()
        intent = results.get("layer1", {}).get("beliefs", {}).get("intent")
        results["layer2"] = await agent2.solve_task(query, intent or {})
    
    return results
```

---

## Critical Success Factors

### 1. **Keep Domain Pure**
- No LLM calls in domain logic
- No database access in domain logic  
- No HTTP requests in domain logic
- Pure functions only → easy to test

### 2. **Agent Harness is the Foundation**
- All agents use the same harness
- Harness handles memory, context, tools
- Agents focus on their specific task

### 3. **State + Replay are Explicit (Now)**
- Every run persists: inputs, outputs, tool calls, timings, versions
- “Confidence/uncertainty” can be heuristic at first (calibrated later)
- This enables debugging and future learning without requiring RL now

### 4. **Memory Enables Learning**
- Episodic memory: specific interactions
- Semantic memory: learned patterns
- Working memory: current context
- Agents get smarter over time

### 5. **State Persistence Enables Future Learning**
- Trajectories can be replayed
- Patterns can be extracted from successful episodes
- RL-style training is optional and explicitly deferred

---

## Testing Strategy

### Unit Tests
```python
# Test domain logic (pure functions)
def test_alignment_scoring_is_deterministic():
    ...
```

### Integration Tests
```python
# Test agent loop
async def test_layer1_agent():
    agent = Layer1Agent()
    
    result = await agent.solve_task(
        user_query="TV for bright room",
        products=[...]
    )
    
    assert "scored_products" in result
    assert result["beliefs"]["uncertainty"] < 0.5
    assert len(result["iterations"]) < 10
```

### End-to-End Tests
```python
# Test full API flow
async def test_agent_api():
    response = await client.post("/agents/query", json={
        "query": "running shoes for marathon",
        "products": [...],
        "client_id": "test"
    })
    
    assert response.status_code == 200
    assert "layer1" in response.json()
    assert "layer2" in response.json()
```

---

## Migration Strategy

### Parallel Implementation
1. Build new agentic architecture alongside existing code
2. No disruption to current functionality
3. Gradual migration of modules to domain layer

### Feature Parity
1. Ensure agents produce same results as old modules
2. A/B test: route some requests to agents, some to old code
3. Compare outputs, measure latency

### Gradual Cutover
1. Start with Layer 1 agent (most mature)
2. Then Layer 2 agent
3. Finally orchestrator
4. Old code stays as fallback

### Deprecation
1. Once agents proven stable (95%+ uptime)
2. Deprecate old monolithic flow
3. Remove legacy code

---

## Next Steps

1. **Read the full architectural doc** (`agentic-arch-transformation.md`)
2. **Start with Phase 1**: Refactor to Clean Architecture
3. **Build agent harness**: This is the foundation everything else depends on
4. **Implement Layer 1 agent**: Test against current implementation
5. **Add Layer 2 agent**: Protocol-based discovery
6. **Deploy orchestrator**: Coordinate both layers

**The goal**: A modular, scalable, theoretically-grounded agentic platform that can learn from outcomes and improve over time.

---

## Questions to Resolve

1. **Orchestrator: Yes or No?**
   - Pro: Intelligent routing, conflict resolution
   - Con: Added complexity, another failure point
   - Recommendation: Start without, add later if needed

2. **How to handle tool failures?**
   - Retry logic in tool executor
   - Fallback strategies per agent
   - Graceful degradation

3. **Memory scope: per-user or per-session?**
   - Per-user: Better long-term learning
   - Per-session: Privacy-friendly
   - Recommendation: Per-user with consent

4. **Real-time vs batch processing?**
   - Real-time: Better UX
   - Batch: Lower cost
   - Recommendation: Hybrid (critical path real-time, learning batch)

---

**Ready to build?** Start with the agent harness. Everything else depends on it.

---

## Appendix: Future Experiment Sketches (Do Not Implement Yet)

The code sketches below are intentionally left as *exploration prompts*.
Keep them out of the critical path until:
1) we have verified outcomes to calibrate against, and
2) we can quantify improvement over the simpler harness.
