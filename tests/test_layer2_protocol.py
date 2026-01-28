from __future__ import annotations

from domain.protocol.scoring import score_structured_match
from domain.protocol.types import ProtocolCandidate, StructuredQuery


def test_structured_match_scores_attribute_and_budget():
    query = StructuredQuery(
        query_text="tv for bright room under 200",
        price_max=200,
        required_attributes=["anti_glare"],
    )
    candidate = ProtocolCandidate(
        id="p1",
        name="Bright TV",
        description="High brightness TV",
        protocol="ucp",
        price=199,
        availability="in_stock",
        attributes={"anti_glare": True},
    )
    match = score_structured_match(query, candidate)
    assert match.score > 0.7
    assert "anti_glare" in match.matched
    assert "price_max" in match.matched


def test_structured_match_penalizes_missing_attribute():
    query = StructuredQuery(
        query_text="headphones", required_attributes=["active_noise_cancellation"]
    )
    candidate = ProtocolCandidate(
        id="p2",
        name="Basic Headphones",
        description="Budget",
        protocol="acp",
        availability="in_stock",
        attributes={},
    )
    match = score_structured_match(query, candidate)
    assert "active_noise_cancellation" in match.missing
    assert match.score < 0.8
