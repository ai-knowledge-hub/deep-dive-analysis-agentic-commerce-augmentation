# Quick Start: ML-Powered Experiment Orchestrator

**5-Minute Setup Guide**

---

## Prerequisites

- ✅ Experiment Orchestrator enhancements installed
- ✅ At least 5 completed experiments in database (for ML training)
- ✅ Python 3.10+ and Next.js running

---

## Step 1: Run Tests (1 minute)

Verify everything works:

```bash
# Backend tests
pytest tests/application/services/test_experiment_statistics.py -v
pytest tests/application/services/test_experiment_ml.py -v

# Expected: All tests pass ✓
```

---

## Step 2: Enable ML Training on Startup (1 minute)

Add to your API startup (e.g., `api/main.py`):

```python
from application.services.experiment_ml_trainer import create_global_trainer
from api.composition import default_deps

# Initialize ML engine on startup
deps = default_deps()
ml_trainer = create_global_trainer(deps)

# Optional: Store trainer globally for access
app.state.ml_trainer = ml_trainer
```

**Alternative (Lazy Loading):**

Update `experiment_orchestrator.py` `_initialize_ml_engine()`:

```python
def _initialize_ml_engine(self) -> None:
    """Load historical experiment data into ML engine."""
    try:
        historical = self._deps.experiments.list_all_experiments(
            status="completed", limit=500
        )
        if len(historical) >= 5:
            self._ml_engine.fit(historical)
            print(f"✓ ML engine trained on {len(historical)} experiments")
    except Exception as e:
        print(f"⚠ ML training skipped: {e}")
```

---

## Step 3: Update Experiments Page UI (2 minutes)

Add visualization components to your experiments page:

```tsx
// In web/app/experiments/page.tsx
import { StatisticalAnalysis } from "@/components/experiments/StatisticalAnalysis";
import { MLPrediction } from "@/components/experiments/MLPrediction";
import { ThompsonSamplingGauge } from "@/components/experiments/ThompsonSamplingGauge";

// In your component, after fetching recommendation:
const recommendation = await getNextTestRecommendation(experimentId, userId);

return (
  <div className="experiments-page">
    {/* Existing experiment UI */}

    {/* New: Recommendation Panel */}
    {recommendation && (
      <div className="recommendation-section">
        <h3>Next Test Recommendation</h3>

        <div className="recommendation-action">
          <p><strong>Action:</strong> {recommendation.action}</p>
          <p><strong>Reason:</strong> {recommendation.reason}</p>
          <p><strong>Confidence:</strong> {(recommendation.confidence * 100).toFixed(0)}%</p>
        </div>

        {/* Statistical Analysis */}
        {recommendation.statistical_analysis && (
          <StatisticalAnalysis
            analysis={recommendation.statistical_analysis}
          />
        )}

        {/* ML Prediction */}
        {recommendation.ml_prediction && (
          <MLPrediction
            prediction={recommendation.ml_prediction}
          />
        )}

        {/* Thompson Sampling */}
        {recommendation.exploration_score && (
          <ThompsonSamplingGauge
            explorationScore={recommendation.exploration_score}
            exploitationScore={recommendation.exploitation_score}
          />
        )}
      </div>
    )}
  </div>
);
```

---

## Step 4: Test End-to-End (1 minute)

1. **Open experiments page** in browser
2. **Click "Recommend Next Test"** on any experiment
3. **Verify new visualizations appear:**
   - ✅ Statistical Analysis card (if 2+ variants tested)
   - ✅ ML Prediction card (if historical data available)
   - ✅ Thompson Sampling gauge (if exploration/exploitation scores present)

---

## Expected Output

### **Console (Backend):**
```
INFO: ML engine training...
INFO: Loaded 247 experiments from database
INFO: ML engine training complete. Loaded 247 experiments.
INFO: Orchestrator initialized with ML engine
```

### **UI (Frontend):**

**Statistical Analysis:**
```
┌─────────────────────────────────────┐
│ Statistical Analysis        [✓ Significant] │
├─────────────────────────────────────┤
│ Comparing: baseline vs hypothesis   │
│ Difference: +15.0%                  │
│ Effect Size: 0.61 (medium)          │
│ P-Value: 0.03 (significant)         │
│ 95% CI: [5.0%, 25.0%]              │
│                                     │
│ Recommendation: Variant B outperforms│
│ A (0.150 lift). Deploy B.          │
└─────────────────────────────────────┘
```

**ML Prediction:**
```
┌─────────────────────────────────────┐
│ ML Prediction          [High Confidence] │
├─────────────────────────────────────┤
│ Intervention: copy                  │
│ Predicted Lift: +12.0%              │
│ Confidence: 73%                     │
│ Based on: 5 similar experiments     │
│                                     │
│ Why? Based on 5 similar successful  │
│ experiments, adding outcome-focused │
│ language improves win-rate...       │
└─────────────────────────────────────┘
```

---

## Troubleshooting

### **"ML engine not trained"**
- **Cause:** Fewer than 5 completed experiments in database
- **Fix:** Run more experiments or lower `min_experiments` in trainer

### **"No statistical_analysis in response"**
- **Cause:** Need at least 2 variants with metrics
- **Fix:** Run experiments on both control and hypothesis variants

### **"Components not rendering"**
- **Cause:** TypeScript/import errors
- **Fix:** Check component imports and ensure files exist

### **"Test failures"**
- **Cause:** Missing dependencies or database schema mismatch
- **Fix:** Run `pip install -r requirements.txt` and check schema

---

## Verify It's Working

### **Backend Check:**
```bash
# Call the API directly
curl http://localhost:8000/experiments/{experiment_id}/next-test?user_id=test

# Should return JSON with:
# - action
# - reason
# - confidence
# - statistical_analysis (if applicable)
# - ml_prediction (if applicable)
# - exploration_score / exploitation_score (if applicable)
```

### **Frontend Check:**
1. Open browser DevTools
2. Go to Network tab
3. Click "Recommend Next Test"
4. Verify response contains new fields
5. Check console for errors

---

## What to Show Clients

### **Demo Script:**

1. **Show an experiment with 2 variants**
   - "Here we tested control vs. hypothesis A"

2. **Click 'Recommend Next Test'**
   - "Our ML system analyzes the results..."

3. **Point out Statistical Analysis**
   - "We use rigorous statistical testing—this shows a **medium effect size** with **p=0.03**, meaning it's statistically significant"

4. **Point out ML Prediction**
   - "Based on 5 similar past experiments, we predict a **12% lift** with **73% confidence**"

5. **Point out Thompson Sampling**
   - "This shows the exploration/exploitation trade-off—we recommend testing this variant because it has high uncertainty"

6. **Show the Action**
   - "The system recommends: **create a new variant** with outcome-focused copy"

---

## Performance Tips

### **For Large Databases (1000+ experiments):**

1. **Limit training data:**
   ```python
   create_global_trainer(deps, max_experiments=500)
   ```

2. **Cache trained engine:**
   ```python
   # Train once, reuse across requests
   global_ml_engine = None

   def get_ml_engine():
       global global_ml_engine
       if global_ml_engine is None:
           trainer = create_global_trainer(deps)
           global_ml_engine = trainer.engine
       return global_ml_engine
   ```

3. **Background training:**
   ```python
   # Train in background thread
   import threading

   def train_async():
       trainer = create_global_trainer(deps)
       app.state.ml_engine = trainer.engine

   threading.Thread(target=train_async).start()
   ```

---

## Next Steps

1. **Collect More Data**
   - Run 10-20 experiments to improve ML predictions
   - Diverse product types improve pattern recognition

2. **Monitor Performance**
   - Track recommendation accuracy
   - Log ML prediction vs. actual lift

3. **Fine-Tune Thresholds**
   - Adjust `min_experiments` based on your data
   - Tune confidence thresholds for your use case

4. **Add More Features**
   - Multi-metric optimization
   - Cross-brand learning
   - LLM-generated hypotheses

---

## Support

- **Docs:** See [`docs/experiment-orchestrator-enhancements.md`](./experiment-orchestrator-enhancements.md)
- **Architecture:** See [`docs/orchestrator-architecture.md`](./orchestrator-architecture.md)
- **Tests:** Run `pytest tests/application/services/test_experiment_*.py -v`

---

**You're Ready! 🚀**

Your ML-powered Experiment Orchestrator is now live with:
- ✅ Statistical significance testing
- ✅ ML pattern recognition
- ✅ Thompson Sampling
- ✅ Beautiful visualizations
- ✅ Production-ready testing

**Ship it and wow your clients!**
