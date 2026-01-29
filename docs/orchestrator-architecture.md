# Experiment Orchestrator Architecture (v2)

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│              EXPERIMENT ORCHESTRATOR (v2)                    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Statistical  │  │  ML Pattern  │  │  Thompson    │     │
│  │  Testing     │  │ Recognition  │  │  Sampling    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                 │                  │              │
│         └─────────────────┴──────────────────┘              │
│                           │                                 │
│                    Decision Engine                          │
│                           │                                 │
└───────────────────────────┼─────────────────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Recommendation  │
                   │  - action       │
                   │  - confidence   │
                   │  - rationale    │
                   └─────────────────┘
```

---

## Decision Flow (Detailed)

```
┌─────────────────────────────────────────────────────────────┐
│ START: suggest_next_test(experiment_id, client_id, user_id) │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Load Experiment Data  │
        │ - variants            │
        │ - metrics             │
        │ - product             │
        │ - brand beliefs       │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Early Exit Cases?   │
        │ - No variants         │──YES──> Recommend: "Create baseline"
        │ - Only 1 variant      │──YES──> Recommend: "Create hypothesis"
        │ - Untested variants   │──YES──> Recommend: "Run untested"
        └───────────┬───────────┘
                    │ NO
                    ▼
        ┌───────────────────────┐
        │ Statistical Analysis  │
        │ - Compare top 2       │
        │ - Welch's t-test      │
        │ - Effect size         │
        │ - Confidence interval │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Stopping Conditions?  │
        │ - p<0.01 & effect>0.5 │──YES──> STOP: "Deploy winner"
        │ - Diminishing returns │──YES──> STOP: "Deploy best"
        └───────────┬───────────┘
                    │ NO
                    ▼
        ┌───────────────────────┐
        │   ML Recommendation   │
        │ - Extract features    │
        │ - Find similar exps   │
        │ - Vote on intervention│
        │ - Predict lift        │
        │ - Calculate confidence│
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  Thompson Sampling    │
        │ - Model uncertainty   │
        │ - Beta distribution   │
        │ - Exploration score   │
        │ - Exploitation score  │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────────────────┐
        │   Priority-Based Decision         │
        │                                   │
        │ 1. ML confidence > 0.6            │
        │    → CREATE variant               │
        │                                   │
        │ 2. Thompson exploration > 0.3     │
        │    → RUN variant (explore)        │
        │                                   │
        │ 3. Sample size < 20               │
        │    → RUN for more data            │
        │                                   │
        │ 4. ML confidence > 0.3            │
        │    → CREATE variant               │
        │                                   │
        │ 5. Fallback                       │
        │    → RUN weakest variant          │
        └───────────┬───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ Return Recommendation │
        │ - action              │
        │ - reason              │
        │ - confidence          │
        │ - payload             │
        │ - statistical_analysis│
        │ - ml_prediction       │
        │ - exploration_score   │
        │ - exploitation_score  │
        └───────────────────────┘
```

---

## Module Interactions

```
┌─────────────────────────────────────────────────────────────┐
│                    ExperimentOrchestrator                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────────┐ ┌──────────────┐ ┌─────────────────┐
│ StatsTesting  │ │  ML Engine   │ │ ThompsonSampler │
│               │ │              │ │                 │
│ compare_      │ │ fit()        │ │ _beta_sample()  │
│ variants()    │ │ predict_best_│ │                 │
│               │ │ hypothesis() │ │ exploration_    │
│ analyze_      │ │              │ │ score           │
│ trend()       │ │ _find_       │ │                 │
│               │ │ similar()    │ │ exploitation_   │
│ detect_       │ │              │ │ score           │
│ diminishing() │ │ _generate_   │ │                 │
│               │ │ hypothesis() │ │                 │
└───────┬───────┘ └──────┬───────┘ └────────┬────────┘
        │                │                  │
        └────────────────┴──────────────────┘
                         │
                         ▼
                 ┌───────────────┐
                 │ BrandBeliefs  │
                 │ Repository    │
                 │               │
                 │ list_beliefs()│
                 └───────────────┘
```

---

## Data Flow Example

### Input:
```json
{
  "experiment_id": "exp_789",
  "client_id": "client_samsung",
  "user_id": "user_123"
}
```

### Internal Processing:

1. **Load Data**
```python
experiment = {
  "id": "exp_789",
  "product_id": "product_tv_001",
  "battery_id": "battery_456",
  "hypothesis": {"metric": "win_rate", "direction": "increase"}
}

variants = [
  {"id": "v1", "label": "Control", ...},
  {"id": "v2", "label": "Hypothesis A", ...},
  {"id": "v3", "label": "Hypothesis B", ...}
]

metrics = [
  {"variant_id": "v1", "metrics": {"win_rate": 0.40, "total_runs": 100}},
  {"variant_id": "v2", "metrics": {"win_rate": 0.55, "total_runs": 100}},
  {"variant_id": "v3", "metrics": {"win_rate": 0.52, "total_runs": 50}}
]

product = {
  "id": "product_tv_001",
  "name": "Samsung QLED 65-inch",
  "description": "4K QLED display with 3000 nits peak brightness, Quantum Processor 4K, 120Hz refresh rate"
}

brand_beliefs = [
  {
    "id": "belief_42",
    "recommendation": "Outcome framing improves glare-reduction intent queries by 63%",
    "confidence": 0.82
  }
]
```

2. **Statistical Analysis**
```python
stat_result = compare_variants(v2, v1, "win_rate")
# Result:
# {
#   "difference": 0.15,
#   "effect_size": 0.61,
#   "p_value": 0.03,
#   "is_significant": True,
#   "confidence_interval": [0.05, 0.25]
# }
```

3. **Check Stopping**
```python
# p=0.03 > 0.01 → Not a clear winner
# No diminishing returns
# → Continue testing
```

4. **ML Prediction**
```python
ml_rec = ml_engine.predict_best_hypothesis(experiment, product, brand_beliefs)
# Result:
# {
#   "hypothesis_type": "copy",
#   "predicted_lift": 0.12,
#   "confidence": 0.73,
#   "rationale": "Based on 5 similar experiments, adding outcome-focused language improves win-rate. Your current copy lacks outcome framing. Brand belief: Outcome framing improves glare-intent queries by 63%.",
#   "suggested_payload": {
#     "description": "Combat glare in bright rooms with 3000-nit peak brightness. Quantum Processor 4K delivers smooth 120Hz gaming without motion blur."
#   }
# }
```

5. **Thompson Sampling**
```python
thompson_choice = {
  "variant_id": "v2",
  "exploration_score": 0.10,  # Low (100 runs)
  "exploitation_score": 0.55  # High (55% win rate)
}
```

6. **Final Decision**
```python
# Priority 1: ML confidence (0.73) > 0.6 → CREATE new variant
return NextTestRecommendation(
  action="create_variant",
  confidence=0.73,
  suggested_label="ML Hypothesis (copy)",
  suggested_payload=ml_rec.suggested_payload,
  ml_prediction=ml_rec,
  statistical_analysis=stat_result
)
```

### Output:
```json
{
  "action": "create_variant",
  "reason": "Based on 5 similar experiments, adding outcome-focused language improves win-rate. Your current copy lacks outcome framing. Brand belief: Outcome framing improves glare-intent queries by 63%.",
  "confidence": 0.73,
  "suggested_label": "ML Hypothesis (copy)",
  "suggested_type": "copy",
  "suggested_payload": {
    "description": "Combat glare in bright rooms with 3000-nit peak brightness. Quantum Processor 4K delivers smooth 120Hz gaming without motion blur."
  },
  "statistical_analysis": {
    "variant_a_id": "v1",
    "variant_b_id": "v2",
    "difference": 0.15,
    "effect_size": 0.61,
    "confidence_interval": [0.05, 0.25],
    "p_value": 0.03,
    "is_significant": true
  },
  "ml_prediction": {
    "hypothesis_type": "copy",
    "predicted_lift": 0.12,
    "confidence": 0.73,
    "similar_experiments": ["exp_123", "exp_456", "exp_789", "exp_101", "exp_234"]
  },
  "exploration_score": null,
  "exploitation_score": null
}
```

---

## Key Algorithms

### 1. Welch's T-Test (Statistical Comparison)

```
Given: variant_a (mean=μ₁, n=n₁), variant_b (mean=μ₂, n=n₂)

Variance (binomial):
  σ₁² = μ₁(1-μ₁)/n₁
  σ₂² = μ₂(1-μ₂)/n₂

Standard error of difference:
  SE = √(σ₁² + σ₂²)

T-statistic:
  t = (μ₂ - μ₁) / SE

Degrees of freedom (Welch-Satterthwaite):
  df = (σ₁² + σ₂²)² / ((σ₁²)²/(n₁-1) + (σ₂²)²/(n₂-1))

P-value:
  p = 2 × P(T > |t|)  [two-tailed]

Effect size (Cohen's d):
  pooled_σ = √((σ₁²(n₁-1) + σ₂²(n₂-1)) / (n₁+n₂-2))
  d = (μ₂ - μ₁) / pooled_σ
```

### 2. Cosine Similarity (ML Feature Matching)

```
Given: current_features (vector), past_features (vector)

Similarity components:
  - Product type match: +0.3
  - Complexity similarity: +0.2 × (1 - |c_current - c_past|)
  - Technical specs match: +0.15
  - Outcome language match: +0.15
  - Win rate similarity: +0.2 × (1 - |w_current - w_past|)

Total similarity score: 0-1
```

### 3. Thompson Sampling (Beta Distribution)

```
Given: wins, total_runs

Beta distribution parameters:
  α = wins + 1
  β = (total_runs - wins) + 1

Sample from Beta(α, β):
  win_rate_sample ~ Beta(α, β)

Exploration score:
  exploration = 1 / √total_runs

Exploitation score:
  exploitation = wins / total_runs

Select variant with highest sampled win_rate
```

---

## Performance Characteristics

### Time Complexity:
- **Statistical comparison:** O(1) - constant time per comparison
- **ML similarity search:** O(n) where n = number of historical experiments
- **Thompson sampling:** O(k) where k = number of variants
- **Overall:** O(n + k) - typically <100ms for n<1000, k<10

### Space Complexity:
- **ML feature database:** O(n × f) where f = feature vector size (~15 features)
- **In-memory:** ~1KB per experiment × 1000 experiments = ~1MB

### Scalability:
- **Current:** Handles 1000s of experiments, 10s of variants
- **Future:** With caching + batch processing, can scale to 100K+ experiments

---

## Configuration & Tuning

### Statistical Thresholds:
```python
SIGNIFICANCE_LEVEL = 0.05  # p < 0.05 for significance
CLEAR_WINNER_P = 0.01      # p < 0.01 for stopping
LARGE_EFFECT_SIZE = 0.5    # Cohen's d > 0.5 for large effect
MIN_SAMPLE_SIZE = 20       # Minimum runs for significance
DIMINISHING_RETURNS = 0.02 # < 2% improvement to stop
```

### ML Thresholds:
```python
HIGH_CONFIDENCE = 0.6      # Create variant immediately
MEDIUM_CONFIDENCE = 0.3    # Create variant as fallback
MIN_SIMILAR_EXPS = 3       # Minimum for pattern voting
SIMILARITY_THRESHOLD = 0.4 # Min similarity for inclusion
```

### Thompson Sampling:
```python
HIGH_EXPLORATION = 0.3     # Explore if score > 0.3
PRIOR_WINS = 1             # Beta prior: α = wins + 1
PRIOR_LOSSES = 1           # Beta prior: β = losses + 1
```

---

## Future Optimizations

1. **Parallel Processing:**
   - Run statistical analysis, ML prediction, Thompson sampling in parallel
   - Expected speedup: 2-3x

2. **Caching:**
   - Cache ML feature vectors
   - Cache similarity scores
   - Expected speedup: 5-10x for repeated queries

3. **Batch Recommendations:**
   - Recommend next N actions, not just 1
   - Support "Run experiments A, B, C in parallel"

4. **Real-Time Learning:**
   - Update ML model incrementally as new experiments complete
   - No need to retrain from scratch

5. **GPU Acceleration:**
   - Use GPU for similarity search (FAISS)
   - Expected speedup: 10-100x for large experiment databases
