from __future__ import annotations

try:
    from fastapi import APIRouter
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore

from modules.intent.llm_classifier import HybridIntentClassifier
from pydantic import BaseModel, Field
from api.utils.tenancy import require_client_id

if APIRouter:
    router = APIRouter(prefix="/intent", tags=["intent"])

    class IntentInferRequest(BaseModel):
        query: str = Field(..., min_length=1)
        user_id: str | None = None
        client_id: str | None = None

    @router.post("/infer")
    def infer_intent(payload: IntentInferRequest):
        require_client_id(payload.client_id, payload.user_id)
        query = payload.query
        classifier = HybridIntentClassifier()
        return {"intent": classifier.classify(query).to_dict()}
else:  # pragma: no cover
    router = None
