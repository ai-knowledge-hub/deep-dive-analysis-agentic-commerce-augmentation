# Production Upgrade Plan – Gemini 3 Hackathon

## 1. Overview
- **Goal:** Transform the agentic commerce platform into a production-grade Gemini-powered experience before **Feb 9 2026**.
- **Core Innovation:** “AI shopping that optimizes empowerment, not addiction.” Every surface must demonstrate values clarification before recommendations.
- **Judging Criteria:** Technical Execution (40 %), Innovation (30 %), Impact (20 %), Presentation (10 %).

## 2. Architecture Delta

| Current Stack | Target Stack |
| --- | --- |
| Keywords → Products | Gemini values dialogue (multi-turn) |
| JSON file memory | SQLite (sessions, users, goals, episodes) + vector sidecars |
| Static scoring | Gemini product reasoning + empowerment scoring |
| Legacy forms | Next.js chat UI + empowerment dashboard |

## 3. Phase Plan

### Phase 1 – Gemini Foundation (Week 1)
1. **Client Module**
   - `gemini/__init__.py` exports high-level helpers.
   - `llm/clients/gemini.py` (new) uses Google GenAI SDK with ADC or `GEMINI_API_KEY`.
   - Retry logic + model priority (`GEMINI_MODEL`, fallback list).
2. **Prompts & Tools (model-agnostic)**
   - `llm/prompts.py`: values clarification, product reasoning, impulse guardian, reflection, intent classifier.
   - `llm/tools.py`: MCP-aligned tool schemas (`product_search`, `compare`, `assess_empowerment`, `generate_reflection`) + execution helpers.
3. **SQLite Data Layer**
   - `db/schema.sql`, `db/connection.py`, and repositories for sessions/goals/turns/episodes/recommendations/semantic memory.
   - Semantic memory moves from JSON to SQLite; add future-ready `embedding` columns.
4. **Dependencies & Config**
   - `requirements.txt` / `pyproject.toml`: add `google-genai`, `google-auth`.
   - `.env.example`: `LLM_PROVIDER`, Gemini keys/models, DB path, `FRONTEND_URL`.

### Phase 2 – Values Agent & Intelligence (Week 2)
1. `gemini/values_agent.py`: WOW feature for goal clarification.
2. `gemini/intent_classifier.py`: hybrid keywords + Gemini semantic fallback (modifies `src/intent/classifier.py`).
3. `gemini/product_reasoner.py`: explains alignment/tradeoffs/confidence.
4. `api/routes/conversation.py` + `api/main.py`: start/continue/goal/recommend/reflect endpoints, CORS for Next.js.
5. **LLM Gateway:** expose `llm.gateway` so orchestration depends on protocol, not provider (DONE).

### Phase 3 – Experience Layer (Week 3)
1. **Next.js App (`web/`)**
   - Layout/landing + chat page.
   - Components: chat window, message bubbles, goal summary, product cards, alignment badges.
   - Empowerment UI: World A vs World B comparison, empowerment gauge, reflection panel.
   - Client libs (`lib/api.ts`, `types.ts`).
2. **Frontend Strategy**
   - Prioritize Next.js chat/dashboard and keep scope tight (no secondary UI).

### Phase 4 – Polish & Demo (Week 4)
1. **Demo Scenarios**
   - Workspace upgrade.
   - “No purchase necessary” impulse interception.
   - Career pivot / learning goals.
2. **Deployment**
   - Backend on Railway (`uvicorn api.main:app`).
   - Frontend on Vercel (set `NEXT_PUBLIC_API_URL`).
   - (Removed) HF Spaces fallback; focus energy on the Next.js experience.

### Phase 5 – Submission (Week 5)
1. 3-minute demo video walking through scenarios.
2. Devpost entry with Gemini integration description, public demo link, GitHub repo.

## 4. Deliverables Matrix

| File / Directory | Purpose | Status |
| --- | --- | --- |
| `gemini/__init__.py` | Module entry | ✅ |
| `llm/clients/gemini.py` | Gemini gateway implementation | ✅ |
| `llm/prompts.py` & `llm/tools.py` | Model-agnostic prompts + tools | ✅ |
| `gemini/values_agent.py` | Values dialogue | ⏳ |
| `gemini/product_reasoner.py` | Alignment explanations | ⏳ |
| `gemini/intent_classifier.py` | Semantic classification | ⏳ |
| `db/schema.sql`, `db/connection.py`, `db/repositories/*` | SQLite backbone | ✅ |
| `api/routes/conversation.py` | Conversation endpoints | ✅ |
| `web/` Next.js app | Frontend | ⏳ |
| `src/intent/classifier.py` | Hybrid classification | ⏳ |
| `.env.example` | Gemini/DB config, `LLM_PROVIDER` | ✅ |
| `requirements.txt` | Add `google-genai` | ✅ |

## 5. Risk Mitigation

| Risk | Mitigation |
| --- | --- |
| Gemini rate limits | Exponential backoff, caching classifiers, hybrid routing with cheaper models. |
| Next.js timeline | Single-track delivery (no alternate UI pivot). |
| SQLite concurrency | `check_same_thread=False`, WAL mode. |
| Free-tier limits | HF Spaces fallback, OpenRouter for low-cost tasks. |

## 6. Success Criteria
- **Technical:** Gemini powers values clarification, intent classification, product reasoning.
- **Innovation:** World A vs World B comparison visible; “no purchase needed” scenario works.
- **Impact:** Demonstrated improvement over traditional commerce.
- **Presentation:** Video clearly explains empowerment-first optimization.

## 7. Research-Driven Enhancements
1. **Context Intelligence:** Hierarchical context packets (session summary → goals → “why this matters” embeddings). Pull from Phenomenology Search + Geometry of Intention research.
2. **Memory Agency:** Long-term semantic + episodic memory with vector sidecars (`sqlite-vec`, pgvector) to recall reflections/lessons.
3. **Hybrid Model Strategy:** Gemini 3 for deep reasoning; OpenRouter or other free models for classification, embeddings, safety reranks.
4. **Multimodal Empowerment:** Gemini vision workflow for catalog imagery (ergonomics, posture, etc.).
5. **Empowerment Imperative Alignment:** Balance freedom of choice with practical guidance—offer reflection, don’t force it.

## 8. Outstanding Questions / Next Steps
- Additional MCP tools (`web_fetch`, `image_analyze`, `memory_write`) with empowerment telemetry.
- Streaming/SSE support for Next.js chat.
- OpenRouter client + routing logic.
- Embedding tables (`semantic_embeddings`, `episode_embeddings`) + vector search integration.
