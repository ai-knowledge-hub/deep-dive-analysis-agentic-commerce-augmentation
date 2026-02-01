# Quick Reference Guide

**Fast lookup for common tasks and commands**

---

## 🚀 Starting the Application

```bash
# Terminal 1: Start Backend API
cd /path/to/project
DATABASE_PATH=./tmp/local.db uv run uvicorn api.main:app --reload --port 8000

# Terminal 2: Start Frontend
cd web
npm run dev
```

**Access:**
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

---

## 🎯 Common User Tasks

### Quick Product Testing (30 seconds)

1. Go to: http://localhost:3000
2. Type query: _"TV for bright room"_
3. Review alignment scores
4. Done!

---

### Run Simulation (2 minutes)

1. Go to: `/simulation`
2. Enter scenario: _"Marathon running shoes"_
3. Click **Run Simulation**
4. Review gap analysis
5. Click **Optimize Against Gap**
6. Click **Retest**
7. Compare before/after scores

---

### Create A/B Experiment (5 minutes)

1. Go to: `/experiments`
2. Click **"Create Battery"** → Name it → Generate queries
3. Click **"Create Experiment"** → Fill form
4. Enable **Lab Mode** (auto-runs control + hypothesis)
5. Click **"Create Experiment"**
6. Wait for results (auto-runs immediately)
7. Review metrics

---

### Load Demo Evidence Data (10 seconds)

1. Go to: `/evidence`
2. Click **"Load Demo Data"**
3. Explore tabs: Evidence / Optimization / Verification

---

## 📊 Navigation Map

| Page | URL | Purpose |
|------|-----|---------|
| **Chat** | `/` | Quick discovery & testing |
| **Overview** | `/overview` | Dashboard summary |
| **Evidence** | `/evidence` | Web research & optimization |
| **Simulation** | `/simulation` | Sandbox testing |
| **Experiments** | `/experiments` | A/B testing & monitoring |
| **Alignment** | `/alignment` | Deep alignment analysis |
| **Admin** | `/admin` | Tenant management |

---

## 🔧 API Quick Reference

### Run Simulation
```bash
curl -X POST http://localhost:8000/simulation/run \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "TV for bright room",
    "product_id": "prod_123",
    "client_id": "client_abc",
    "user_id": "user_xyz"
  }'
```

### Create Experiment
```bash
curl -X POST http://localhost:8000/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Outcome Framing Test",
    "product_id": "prod_123",
    "battery_id": "battery_789",
    "user_id": "user_xyz"
  }'
```

### Search Products
```bash
curl "http://localhost:8000/products/search?q=TV&client_id=client_abc"
```

---

## 📈 Key Metrics Explained

| Metric | Range | Meaning | Good Value |
|--------|-------|---------|------------|
| **Alignment Score** | 0-1 | Product-goal match confidence | ≥ 0.7 |
| **Win Rate** | 0-100% | % queries where variant wins | ≥ 60% |
| **Avg Score** | 0-1 | Mean alignment across queries | ≥ 0.6 |
| **Lift** | -100% to ∞ | % improvement vs baseline | ≥ 25% |
| **Confidence** | 0-1 | Statistical certainty | ≥ 0.7 |
| **Effect Size** | 0-∞ | Magnitude of difference | ≥ 0.5 |
| **P-Value** | 0-1 | Statistical significance | ≤ 0.05 |

---

## 🎨 Color Coding

| Color | Meaning | Used For |
|-------|---------|----------|
| **Green (#1cc886)** | Success / High | Confidence ≥70%, Good alignment |
| **Yellow (#fbbf24)** | Medium / Warning | Confidence 50-70%, Medium alignment |
| **Orange (#fb923c)** | Low / Attention | Confidence <50%, Low alignment |
| **Blue (#3b82f6)** | Info / Metadata | Tags, secondary info |
| **Red (#ef4444)** | Error / Negative | Failures, negative lift |

---

## 💡 Best Practice Checklist

### Before Running Experiments:
- [ ] Product has description
- [ ] Query battery has 10+ queries
- [ ] At least 2 variants created
- [ ] Hypothesis documented

### For Good Results:
- [ ] Run 15+ queries in battery
- [ ] Test for 1 week minimum
- [ ] Use Lab Mode for automation
- [ ] Monitor daily

### Optimization Tips:
- [ ] Start with chat to identify gaps
- [ ] Test in simulation first
- [ ] Validate with experiments
- [ ] Schedule recurring runs

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| **Low alignment scores** | Run simulation → see gap → optimize |
| **No stat significance** | Need more data or bigger variant difference |
| **Empty results** | Check product context (client/brand selected?) |
| **Evidence page empty** | Run a chat query first; Evidence syncs from latest session |
| **Chat doesn't understand** | Be specific: "TV for bright room" not just "TV" |

---

## 📝 Common JSON Payloads

### Experiment Hypothesis
```json
{
  "metric": "win_rate",
  "direction": "increase",
  "rationale": "Outcome framing improves discoverability"
}
```

### Variant Payload (Copy Test)
```json
{
  "description": "Support longer runs with cushioning that eases joint strain"
}
```

### Competitor Policy
```json
{
  "competitor_client_ids": ["client-nike", "client-adidas"],
  "strategy": "hold_constant"
}
```

---

## 🔑 Keyboard Shortcuts (Frontend)

| Key | Action |
|-----|--------|
| `/` | Focus chat input |
| `Esc` | Close modals/drawers |
| `Cmd/Ctrl + K` | Quick navigation |

---

## 📚 Documentation Index

| Document | Purpose |
|----------|---------|
| [User Guide Complete](./user-guide-complete.md) | Full user manual |
| [Architecture Visual](./architecture-visual.md) | System diagrams |
| [Quick Reference](./quick-reference.md) | This document |
| [Experiment Orchestrator](./experiment-orchestrator-enhancements.md) | ML automation |
| [Brand Beliefs](./brand-belief-system.md) | Knowledge accumulation |
| [Evidence Flow](./evidence-first-flow.md) | Evidence discovery |

---

## 🆘 Getting Help

1. **Check documentation** (you're here!)
2. **Run a chat query** to generate evidence data
3. **Review error logs** (console in browser DevTools)
4. **Check API docs** (http://localhost:8000/docs)

---

## 🎓 Learning Path

**Day 1: Exploration**
- [ ] Start with chat interface
- [ ] Try multiple queries
- [ ] Open Evidence + Explanation + Next actions tabs

**Day 2: Simulation**
- [ ] Create first simulation
- [ ] Review gap analysis
- [ ] Test optimization
- [ ] Save lesson

**Week 1: Experiments**
- [ ] Create query battery
- [ ] Set up first experiment (Lab Mode)
- [ ] Monitor results
- [ ] Try ML recommendation

**Week 2: Optimization**
- [ ] Schedule recurring runs
- [ ] A/B test variants
- [ ] Track trends
- [ ] Review brand beliefs

---

**Quick Wins:**
1. Load evidence demo → See optimization → 5 minutes
2. Chat "TV for bright room" → See alignment → 1 minute
3. Run simulation → See gap → Optimize → 3 minutes

**Ready to optimize? Start with the chat! 🚀**
