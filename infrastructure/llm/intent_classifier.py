from __future__ import annotations

from typing import Any, Dict

from shared.replay.versions import default_versions
from infrastructure.db import replays as replays_repo
from infrastructure.llm.gateway import generate
from infrastructure.llm.hybrid_intent_classifier import HybridIntentClassifier
from infrastructure.llm.intent_taxonomy import INTENT_TAXONOMY
from infrastructure.llm.prompts import INTENT_CLASSIFICATION_PROMPT
from shared.agents.replay_logger import ReplayLogger, ReplayRecord
from domain.intent import keyword_classifier


def build_intent_classifier(*, threshold: float = 0.55) -> HybridIntentClassifier:
    return HybridIntentClassifier(
        threshold=threshold,
        generate_fn=generate,
        keyword_classify_fn=lambda text, **kwargs: keyword_classifier.classify(
            text, taxonomy=INTENT_TAXONOMY, **kwargs
        ),
        prompt_template=INTENT_CLASSIFICATION_PROMPT,
    )


def log_intent_replay(
    *,
    query: str,
    result: Dict[str, Any],
    context_used: bool,
    client_id: str,
    user_id: str | None = None,
    session_id: str | None = None,
) -> None:
    replay = ReplayRecord(
        run_type="intent.infer",
        inputs={"query": query, "context_used": context_used},
        outputs={
            "primary_goal": result.get("primary_goal"),
            "confidence": result.get("confidence"),
            "source": result.get("source"),
        },
        tool_calls=[],
        versions=default_versions(scoring_version="intent-v1"),
    )
    logger = ReplayLogger(persist_fn=replays_repo.create_replay_record)
    logger.persist(
        run_type="intent.infer",
        record=replay,
        client_id=client_id,
        user_id=user_id,
        session_id=session_id,
        entity_type="conversation_session" if session_id else None,
        entity_id=session_id,
    )


def classify_intent(
    query: str,
    *,
    context: str | None = None,
    client_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> Dict[str, Any]:
    """Thin wrapper around the current intent classifier.

    When `client_id` is provided, this also writes a replay record for audit/debug.
    """
    classifier = build_intent_classifier()
    result = classifier.classify(query, context=context).to_dict()
    if not client_id:
        return result

    log_intent_replay(
        query=query,
        result=result,
        context_used=bool(context),
        client_id=client_id,
        user_id=user_id,
        session_id=session_id,
    )
    return result


__all__ = ["build_intent_classifier", "classify_intent", "log_intent_replay"]
