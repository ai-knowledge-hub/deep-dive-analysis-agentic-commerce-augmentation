# Complete User Guide: Intent-Legible Commerce Platform

**Version:** 1.0
**Date:** 2026-01-29
**For:** Brand Marketing Managers, E-commerce Teams, and Integration Partners

---

## Table of Contents

1. [What This Platform Does](#what-this-platform-does)
2. [Who Should Use This](#who-should-use-this)
3. [Getting Started](#getting-started)
4. [Core Workflows](#core-workflows)
5. [Feature Deep Dives](#feature-deep-dives)
6. [Best Practices](#best-practices)
7. [Glossary](#glossary)
8. [Troubleshooting](#troubleshooting)

---

## What This Platform Does

### The Problem

When AI agents (ChatGPT, Gemini, Claude) recommend products to users, they struggle with **intent alignment**:

- ❌ **AI can't tell if a product actually solves the user's goal**
  - User: "I need a TV for a bright room"
  - AI sees: "65-inch 4K QLED, 3000 nits brightness"
  - AI doesn't know: "3000 nits solves glare problems in bright rooms"

- ❌ **Product descriptions are written for humans, not AI**
  - Brands list specs: "M3 chip, 16GB RAM, 512GB SSD"
  - AI needs capabilities: "Runs creative software smoothly for design work"

- ❌ **No way to test if optimizations actually work**
  - Marketing rewrites product copy
  - Nobody knows if it improved AI discoverability

### The Solution

This platform provides a **complete optimization cycle** for AI commerce discovery:

1. **Intent Inference** — Understand what users actually want (not just what they said)
2. **Product Profiling** — Transform specs into capability-based representations
3. **Alignment Scoring** — Rate how well products match inferred goals
4. **Simulation Testing** — Test improvements before deployment
5. **Verification** — Measure discoverability lift (before/after)
6. **Automated Experimentation** — Systematically A/B test product descriptions

---

## Who Should Use This

### Primary User: **Brand Marketing Manager**

**Your Goals:**
- Increase product visibility in AI agent recommendations
- Improve conversion from AI-driven traffic
- Optimize product descriptions for AI commerce
- Measure impact of optimizations

**What You'll Do:**
- Chat with the platform to discover gaps in product descriptions
- Run simulations to test improvements before deployment
- Set up A/B experiments for systematic optimization
- Monitor trends in win rates and alignment scores

---

### Secondary User: **E-commerce Developer**

**Your Goals:**
- Integrate intent alignment into your commerce stack
- Add AI-powered product search to your website
- Implement UCP/ACP commerce protocols

**What You'll Do:**
- Use the conversation API for chat interfaces
- Call simulation API to validate product copy
- Check protocol readiness scores
- Subscribe to webhook events

---

### Tertiary User: **Product Manager / Merchandiser**

**Your Goals:**
- Understand which products resonate with AI agents
- Identify high-priority products for optimization
- Track performance across product catalog

**What You'll Do:**
- Review alignment scores across products
- Analyze simulation lessons to identify patterns
- Monitor experiment trends for category insights

---

## Getting Started

### Step 1: Sign In

Navigate to `http://localhost:3000` and sign in with Clerk authentication.

**What you'll see:**
- Sidebar with navigation to all features
- Home page with chat interface
- Product selector (if you have multiple brands)

---

### Step 2: Select Your Brand/Product Context

**Top Navigation:**
- **Client** — Your organization (e.g., "Nike")
- **Brand** — Product line (e.g., "Air Max")
- **Product** — Specific item (optional, for product-specific work)

This context determines which products appear in search results and experiments.

---

### Step 3: Try the Chat Interface (Quickest Way to Understand)

**What to do:**
1. Type a query: _"What TV works well in bright rooms?"_
2. Watch the platform:
   - Infer your goal ("reduce glare in bright environment")
   - Clarify missing context ("What room size?", "Budget?")
   - Search your product catalog
   - Score products by alignment
   - Show reasoning ("This TV has 3000 nits → reduces glare")

**Why this matters:**
This is what AI shopping agents do when customers ask questions. The platform shows you exactly how your products perform.

---

## Core Workflows

### Workflow 1: Quick Discovery (Chat Interface)

**Use Case:** "I want to see how my products perform for a specific user query"

**Steps:**
1. Go to **Home** (/)
2. Enter a user query (e.g., "laptop for video editing")
3. Review:
   - **Inferred Goals** — What the AI understood
   - **Product Results** — Your products ranked by alignment
   - **Reasoning** — Why each product scored high/low
4. Click **"Run Evidence Analysis"** to see open-web comparisons
5. Click **"Optimize Description"** to get improvement suggestions

**Time:** ~2 minutes
**Output:** Immediate insight into product discoverability

---

### Workflow 2: Simulation Testing

**Use Case:** "I want to test if a description change will improve discoverability before I deploy it"

**Steps:**

1. **Go to Simulation Page** (`/simulation`)

2. **Create New Simulation:**
   - Enter test scenario: _"Show me running shoes for marathon training"_
   - Click **"Run Simulation"**

3. **Review Gap Analysis:**
   - See what capabilities are missing
   - Example: "Product lacks outcome signals for 'endurance support'"

4. **Optimize Description:**
   - Click **"Optimize Against Gap"**
   - Review suggested improvements
   - Example: "Support longer runs with cushioning that eases joint strain"

5. **Retest:**
   - Click **"Retest with Optimized Copy"**
   - Compare scores:
     - Before: 0.42 alignment
     - After: 0.71 alignment
     - **+69% improvement**

6. **Save Lesson:**
   - Platform automatically saves what worked
   - Example: "Outcome framing improves marathon-intent queries by 69%"

**Time:** ~5 minutes
**Output:** Validated improvement before deployment

---

### Workflow 3: Controlled Experiments (Systematic A/B Testing)

**Use Case:** "I want to systematically test product description variants and track performance over time"

**Steps:**

#### **Part A: Create Query Battery** (Test Scenarios)

1. **Go to Experiments Page** (`/experiments`)

2. **Click "Query Battery Builder"**

3. **Create Battery:**
   - Name: "Bright Room TV Tests"
   - Purpose: "Test TV descriptions for bright room scenarios"
   - Generation mode: "Bottom-up" (generates from product) or "Top-down" (from seed queries)

4. **Generate Queries:**
   - Platform creates test scenarios:
     - "TV that won't glare in bright room"
     - "Television for sunny living room"
     - "Anti-glare TV for daytime viewing"

5. **Review & Edit:**
   - Enable/disable queries
   - Adjust weights
   - Delete irrelevant ones

---

#### **Part B: Create Experiment**

1. **Click "Create Experiment"**

2. **Fill in Form:**
   - Name: "Outcome Framing Test"
   - Battery: Select "Bright Room TV Tests"
   - Hypothesis: _"Outcome-focused language improves discoverability by 15%"_
   - (Optional) Competitor Policy: Which competitor products to hold constant

3. **Lab Mode vs Manual:**
   - **Lab Mode** (recommended): Platform auto-creates control + hypothesis variants and runs tests
   - **Manual Mode**: You create variants yourself

---

#### **Part C: Create Variants** (if Manual Mode)

1. **Click "Add Variant"**

2. **Control Variant:**
   - Label: "Control (current copy)"
   - Type: "copy"
   - Payload: `{}` (uses existing product description)

3. **Hypothesis Variant:**
   - Label: "Outcome-Focused Copy"
   - Type: "copy"
   - Payload:
     ```json
     {
       "description": "Combat glare in bright living rooms with 3000-nit peak brightness. Enjoy TV without closing blinds."
     }
     ```

4. **Click "Run Battery"** on each variant

---

#### **Part D: Monitor Results**

1. **View Metrics:**
   - Win rate: % of queries where variant won
   - Avg score: Mean alignment score
   - Trend: Sparkline showing performance over time

2. **Get AI Recommendation:**
   - Click **"Recommend Next Test"**
   - Platform analyzes:
     - Statistical significance
     - ML pattern recognition
     - Thompson Sampling (exploration/exploitation)
   - Suggests: _"Create new variant testing technical detail reduction (confidence: 73%)"_

3. **Schedule Recurring Runs:**
   - Enable schedule
   - Set interval (e.g., daily)
   - Platform auto-runs and tracks trends

**Time:** ~15 minutes setup, ongoing monitoring
**Output:** Systematic optimization with trend analysis

---

### Workflow 4: Evidence Discovery

**Use Case:** "I want to see how my products compare to open-web representations"

**Steps:**

1. **Go to Evidence Page** (`/evidence`)

2. **Load Demo Data** (or run from chat):
   - Click **"Load Demo Data"** to explore
   - Or: Run evidence analysis from chat interface

3. **Review Evidence Tab:**
   - See products ranked by confidence
   - View current descriptions
   - See optimized descriptions (green highlight)

4. **Switch to Optimization Tab:**
   - See before/after comparisons
   - View improvement scores
   - Understand spec → outcome transformation

5. **Switch to Verification Tab:**
   - See discoverability metrics:
     - Before: 3 products discovered
     - After: 5 products discovered
     - **+67% lift**
   - Read insight panel for explanation

**Time:** ~3 minutes
**Output:** Evidence-based optimization recommendations

---

## Feature Deep Dives

### Overview Dashboard (`/overview`)

**Purpose:** Single-pane-of-glass for platform activity

**What you see:**
- **Simulation Sandbox**
  - Total simulations run
  - Average alignment score
  - Top lesson learned
- **Evidence + Research**
  - Evidence analyses run
  - Average lift from optimizations
  - Discovery improvement
- **Experiments**
  - Active experiments count
  - Win rate trend (sparkline)
  - Latest recommendation
- **Alignment**
  - Total products scored
  - Average alignment
  - High-performing product count

**Best Practices:**
- Check daily to monitor trends
- Click sparklines to drill into experiments
- Review top lessons to identify patterns

---

### Alignment Page (`/alignment`)

**Purpose:** Full alignment analysis and research results

**What you see:**
- Product alignment scores across queries
- Goal breakdowns
- Research evidence
- Capability gaps

**When to use:**
- Deep-dive analysis of specific products
- Understanding why alignment is low
- Researching competitor positioning

---

### Admin Page (`/admin`)

**Purpose:** Multi-tenant management

**What you can do:**
- Manage clients (organizations)
- Create brands
- Add products
- Manage users
- Configure platform profiles (UCP/ACP readiness)

**Who uses this:**
- Platform administrators
- Integration partners
- Enterprise account managers

---

## Best Practices

### 1. Start with Chat, Graduate to Experiments

**Why:**
- Chat gives you immediate feedback
- Simulations let you test ideas quickly
- Experiments provide systematic validation

**Example Journey:**
```
Day 1: Chat → "Hmm, my running shoes score low for marathon queries"
Day 2: Simulation → "Adding 'endurance support' improves score by 60%"
Day 3: Experiment → "Let's A/B test this systematically"
Week 2: Monitoring → "Confirmed: +45% win rate improvement"
```

---

### 2. Use Lab Mode for New Experiments

**Why:**
- Platform auto-generates control + hypothesis variants
- Runs tests immediately
- Provides ML-based next-test recommendations

**When to use Manual Mode:**
- You have very specific variants to test
- You want full control over timing
- You're testing complex multi-factor changes

---

### 3. Schedule Recurring Experiments

**Why:**
- Detects regressions (if competitors improve)
- Tracks seasonal trends
- Builds statistical confidence over time

**How:**
- Set interval to match content update frequency
- Use 1440 minutes (daily) for active optimization
- Use 10080 minutes (weekly) for stable monitoring

---

### 4. Monitor Brand Beliefs

**Purpose:** Track what you've learned about your brand

**How it works:**
- After each experiment, platform generates a "belief"
- Example: _"Outcome framing improves glare-intent queries by 63%"_
- Beliefs accumulate into brand knowledge

**Where to see:**
- Experiments page → "Brand Belief" section
- Beliefs API: `GET /beliefs?brand_id=your-brand`

---

### 5. Use Query Batteries Strategically

**Bottom-Up Generation:**
- Use when: You know the product, need to find relevant queries
- Example: TV product → generates "bright room TV", "anti-glare television", etc.

**Top-Down Generation:**
- Use when: You know customer queries, need to test against them
- Example: Seed with "marathon shoes" → generates variations

**Hybrid:**
- Use both and merge

---

## Glossary

| Term | Definition | Example |
|------|------------|---------|
| **Intent Inference** | LLM models user goal from query + context | "TV for bright room" → Goal: "reduce glare in bright environment" |
| **Intentionality Profile** | Product representation as capabilities→outcomes | Specs: "3000 nits" → Capability: "high brightness" → Outcome: "clear picture in daylight" |
| **Alignment Score** | Confidence that product solves user's goal (0-1) | 0.71 = 71% confident this product meets the goal |
| **Gap Analysis** | Missing capabilities vs. user goal | Goal needs "endurance support", product lacks it |
| **Discoverability Lift** | % improvement in recommendation probability | Before: 3 products found, After: 5 found = +67% lift |
| **Query Battery** | Collection of test scenarios for a product | "Bright Room TV Tests" with 15 test queries |
| **Variant** | A/B test version (e.g., different product copy) | Control vs. "Outcome-Focused Copy" |
| **Simulation Run** | One-time test execution with gap analysis | Test scenario → score → gap → optimize → retest |
| **Experiment** | Ongoing test with recurring runs and metrics | "Outcome Framing Test" running daily for 2 weeks |
| **Win Rate** | % of queries where variant beats control | Variant A wins 12 of 15 queries = 80% win rate |
| **Protocol Readiness** | UCP/ACP compliance score for commerce platforms | "UCP ready: 85%, ACP ready: 92%" |
| **Brand Belief** | Learned insight about what works for your brand | "Technical detail reduction helps footwear (confidence: 0.82)" |

---

## Troubleshooting

### Q: Chat doesn't understand my query

**A:** Be specific about the user's goal, not just the product category.

❌ Bad: "shoes"
✅ Good: "running shoes for marathon training on roads"

---

### Q: Products score low in alignment

**A:** This means your product descriptions lack outcome signals.

**Fix:**
1. Run simulation to see gap analysis
2. Optimize description with suggested capabilities
3. Retest to measure improvement

---

### Q: Experiment shows no statistically significant difference

**A:** This could mean:
1. **Variants are too similar** — Try a more dramatic change
2. **Not enough data** — Run more tests or increase query battery size
3. **Product actually doesn't match queries** — Review gap analysis

---

### Q: Simulation score is still low after optimization

**A:** Check:
1. **Does the product actually solve the goal?** (Platform can't fix fundamental product-market fit issues)
2. **Are you testing against the right scenarios?** (TV for bright rooms won't help if testing "gaming performance")
3. **Is the optimized copy realistic?** (Don't claim capabilities the product doesn't have)

---

### Q: How do I integrate this into my product feed?

**A:** Two options:

**Option 1: Manual Update**
1. Run experiment to find winning variant
2. Copy optimized description
3. Update product feed manually

**Option 2: API Integration**
1. Call `POST /simulation/run` for each product
2. Parse `gap_analysis` response
3. Call `POST /simulation/optimize` to get improved copy
4. Automatically update product feed via your CMS

---

### Q: What's the difference between Simulation and Experiments?

**A:**

| Feature | Simulation | Experiments |
|---------|-----------|-------------|
| **Purpose** | Quick testing | Systematic validation |
| **Speed** | Instant | Recurring over time |
| **Data** | Single run | Trend analysis |
| **Use Case** | "Does this idea work?" | "Which variant performs best?" |
| **Output** | Gap analysis + optimization | Win rate, statistical significance |

---

### Q: Can I test against competitor products?

**A:** Yes! Use "Competitor Policy" in experiments:

```json
{
  "competitor_client_ids": ["client-nike", "client-adidas"],
  "strategy": "hold_constant"
}
```

This holds competitor products constant while testing your variants.

---

### Q: How often should I run experiments?

**A:**

- **Active optimization:** Daily
- **Monitoring stable products:** Weekly
- **Seasonal products:** Before peak season
- **New product launches:** Daily for first 2 weeks, then weekly

---

## Advanced Features

### Thompson Sampling (Exploration/Exploitation)

**What it does:** Balances testing new variants vs. exploiting known winners

**How to see it:**
- Click "Recommend Next Test" in experiments
- View "Thompson Sampling Gauge"
- Shows: Exploration score vs. Exploitation score

**When to trust it:**
- High exploration score → Platform recommends testing a new variant
- High exploitation score → Platform recommends running the current winner more

---

### ML-Based Recommendations

**What it does:** Learns from past experiments to predict promising variants

**How it works:**
1. Platform analyzes all historical experiments
2. Finds patterns (e.g., "outcome framing works well for electronics")
3. Recommends next variant with predicted lift

**Requirements:**
- At least 5 completed experiments
- Experiments with 2+ variants
- Metrics data (win rate, avg score)

**Where to see:**
- Experiments page → "Recommend Next Test" button
- Shows: Confidence, predicted lift, rationale

---

### Brand Belief System

**What it does:** Accumulates learned insights about your brand

**How it works:**
1. After each experiment, platform generates a belief
2. Belief includes: hypothesis, evidence, confidence
3. Future recommendations use beliefs as context

**Example:**
```
Belief: "Outcome framing improves glare-intent queries by 63%"
Evidence: { win_rate_lift: 0.63, sample_size: 47 }
Confidence: 0.82
```

**Where to see:**
- Experiments page → "Brand Belief" section
- Shows: Latest belief with confidence badge
- Future: Full belief history with trends

---

## Integration Guide (for Developers)

### REST API

Base URL: `http://localhost:8000`

**Authentication:** Pass `user_id` and `client_id` in request body

**Example: Run Simulation**
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

**Example: Create Experiment**
```bash
curl -X POST http://localhost:8000/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Outcome Framing Test",
    "product_id": "prod_123",
    "brand_id": "brand_456",
    "battery_id": "battery_789",
    "hypothesis": {"metric": "win_rate", "direction": "increase"},
    "user_id": "user_xyz",
    "client_id": "client_abc"
  }'
```

**Full API Docs:** See `docs/api-reference.md` (to be created)

---

## Conclusion

This platform provides a **complete optimization cycle** for AI commerce discovery:

1. **Understand** user intent (chat interface)
2. **Profile** your products (intentionality profiling)
3. **Test** improvements (simulation sandbox)
4. **Validate** systematically (controlled experiments)
5. **Monitor** trends (metrics & beliefs)
6. **Iterate** with AI guidance (ML recommendations)

**Next Steps:**
1. Try the chat interface with a real customer query
2. Run a simulation on your lowest-performing product
3. Set up your first experiment with Lab Mode
4. Schedule recurring runs
5. Monitor the dashboard daily

**Need Help?**
- Check troubleshooting section above
- Review docs: `docs/` folder
- Contact: support@intentionality.ai (if applicable)

---

**Happy Optimizing! 🚀**

Your products are about to become a lot more discoverable to AI shopping agents.
