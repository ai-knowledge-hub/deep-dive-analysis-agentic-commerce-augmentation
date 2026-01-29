"""Infrastructure research agent runner (LLM + tools + replay logging).

This module owns IO:
- LLM calls
- tool execution loop
- optional replay persistence

Pure helpers live in `domain.conversation.research`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from domain.conversation import research as research_domain
from infrastructure.db import replays as replays_repo
from infrastructure.llm.gateway import generate as generate
from infrastructure.llm.gateway import generate_with_tools as generate_with_tools
from infrastructure.agents.agent_loop import AgentLoop
from infrastructure.agents.tool_registry import ToolRegistry
from shared.agents.context_manager import ContextManager, PromptBudget
from shared.agents.replay_logger import ReplayLogger, ReplayRecord, ToolCall
from shared.config.env import settings
from shared.replay.versions import default_versions


RESEARCH_PROMPT = """You are a product gap research agent.

Goal: Provide neutral discovery research when product data is thin.
Return a concise bullet summary with citations, plus risks and uncertainty.
Never fabricate sources. If data is unavailable, say so explicitly.
"""


GenerateFn = Callable[[str], Any]
GenerateWithToolsFn = Callable[[str, list, Optional[str], Optional[str]], Any]


def run_research(
    query: str,
    goals: List[str],
    context: str | None = None,
    *,
    client_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    generate_fn: GenerateFn | None = None,
    generate_with_tools_fn: GenerateWithToolsFn | None = None,
    prompt_template: str | None = None,
) -> dict:
    """Generate a research bundle using MCP tools (web_fetch, etc.)."""
    generate_fn = generate_fn or generate
    generate_with_tools_fn = generate_with_tools_fn or generate_with_tools
    prompt_template = prompt_template or RESEARCH_PROMPT
    tool_registry = ToolRegistry()
    goal_block = "\n".join(f"- {goal}" for goal in goals) or "- (no explicit goals)"
    context_manager = ContextManager(
        budget=PromptBudget(max_context_chars=2200, max_prompt_chars=14000)
    )
    prompt = context_manager.research_prompt(
        template=prompt_template,
        query=query,
        goals_block=goal_block,
        context=context,
    )

    response: dict
    tool_calls: List[dict] = []
    tool_outputs: List[dict] = []
    tool_call_records: List[ToolCall] = []
    try:
        if settings.llm_provider == "openrouter" and not settings.openrouter_api_key:
            raise RuntimeError("OpenRouter API key missing")
        loop = AgentLoop(
            tools=tool_registry, generate_with_tools_fn=generate_with_tools_fn
        )
        tool_run, _ = loop.run_tools_once(
            prompt=prompt,
            run_type="conversation.research.llm",
            inputs={"query": query, "goals": goals, "context_used": bool(context)},
            versions=default_versions(),
        )
        response = tool_run.model_response
        tool_calls = tool_run.tool_calls
        tool_outputs = tool_run.tool_outputs
        tool_call_records = tool_run.tool_call_records
    except Exception as exc:
        response = {"text": "", "error": str(exc)}
        tool_calls = (
            response.get("tool_calls", []) if isinstance(response, dict) else []
        )
        for call in tool_calls:
            name = call.get("name")
            args = call.get("args", {})
            execution = tool_registry.execute_with_record(
                name or "tool", args if isinstance(args, dict) else {}
            )
            tool_outputs.append({"name": name, "output": execution.output})
            tool_call_records.append(execution.call)

    confidence, breakdown = _estimate_confidence(
        query=query,
        goals=goals,
        response=response,
        tool_outputs=tool_outputs,
        generate_fn=generate_fn,
    )

    insights = research_domain.build_insights(
        response=response,
        confidence=confidence,
        query=query,
        goals=goals,
        tool_outputs=tool_outputs,
    )

    replay = ReplayRecord(
        run_type="conversation.research",
        inputs={"query": query, "goals": goals, "context_used": bool(context)},
        outputs={"confidence": confidence, "insights_count": len(insights)},
        tool_calls=tool_call_records,
        versions=default_versions(),
    )

    payload: Dict[str, Any] = {
        "query": query,
        "goals": goals,
        "context_used": bool(context),
        "model_response": response,
        "tool_calls": tool_calls,
        "tool_outputs": tool_outputs,
        "confidence": confidence,
        "confidence_breakdown": breakdown,
        "insights": insights,
        "replay": replay.to_dict(),
    }

    if client_id:
        logger = ReplayLogger(persist_fn=replays_repo.create_replay_record)
        replay_row = logger.persist(
            run_type="conversation.research",
            record=replay,
            client_id=client_id,
            user_id=user_id,
            session_id=session_id,
            entity_type="conversation_session" if session_id else None,
            entity_id=session_id,
        )
        payload["replay_id"] = replay_row.get("id")

    return payload


def _estimate_confidence(
    *,
    query: str,
    goals: List[str],
    response: Dict[str, object] | str | None,
    tool_outputs: List[dict],
    generate_fn: GenerateFn,
) -> tuple[float, dict]:
    heuristic_score, heuristic_detail = research_domain.estimate_confidence_heuristic(
        query=query, goals=goals, response=response, tool_outputs=tool_outputs
    )
    llm_score, llm_detail = _llm_confidence(
        query=query,
        goals=goals,
        response=response,
        tool_outputs=tool_outputs,
        generate_fn=generate_fn,
    )

    if llm_score is None:
        blended = heuristic_score
        llm_weight = 0.0
    else:
        llm_weight = 0.3
        blended = (0.7 * heuristic_score) + (llm_weight * llm_score)

    blended = max(0.0, min(1.0, blended))
    return blended, {
        "heuristic": heuristic_detail,
        "llm": llm_detail,
        "blended": blended,
    }


def _llm_confidence(
    *,
    query: str,
    goals: List[str],
    response: Dict[str, object] | str | None,
    tool_outputs: List[dict],
    generate_fn: GenerateFn,
) -> tuple[float | None, dict]:
    if settings.llm_provider == "openrouter" and not settings.openrouter_api_key:
        return None, {"status": "skipped", "reason": "openrouter_api_key missing"}
    if settings.llm_provider == "gemini" and not settings.gemini_api_key:
        return None, {"status": "skipped", "reason": "gemini_api_key missing"}

    text = research_domain.extract_text(response)
    tools_text = research_domain.tool_summary(tool_outputs)
    prompt = research_domain.confidence_prompt(query, goals, text, tools_text)
    try:
        raw = generate_fn(prompt)
    except Exception as exc:
        return None, {"status": "error", "reason": str(exc)}

    score = research_domain.parse_confidence(str(raw))
    if score is None:
        return None, {"status": "invalid", "raw": str(raw)}
    return score, {"status": "ok", "score": score, "raw": str(raw).strip()}


__all__ = ["RESEARCH_PROMPT", "run_research"]
