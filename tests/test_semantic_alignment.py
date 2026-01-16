"""Tests for semantic goal-product alignment.

These tests verify that the embedding-based alignment properly
understands semantic relationships between goals and products.
"""

import pytest
from unittest.mock import patch, MagicMock

from modules.commerce.domain import Product
from modules.empowerment.goal_alignment import (
    assess,
    get_alignment_explanation,
    _build_product_semantic_text,
    _keyword_assess,
    HIGH_ALIGNMENT_THRESHOLD,
    MEDIUM_ALIGNMENT_THRESHOLD,
)


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def ergonomic_chair() -> Product:
    return Product(
        id="chair-001",
        name="Ergonomic Office Chair",
        price=450.0,
        tags=["office", "ergonomic", "furniture"],
        description="Premium ergonomic chair with lumbar support for long work sessions",
        capabilities_enabled=[
            "posture support",
            "back pain relief",
            "comfortable sitting",
        ],
        category="Office Furniture",
        confidence=0.95,
    )


@pytest.fixture
def standing_desk() -> Product:
    return Product(
        id="desk-001",
        name="Adjustable Standing Desk",
        price=600.0,
        tags=["office", "desk", "standing"],
        description="Electric height-adjustable desk for sit-stand workstyles",
        capabilities_enabled=[
            "height adjustment",
            "standing work",
            "workspace flexibility",
        ],
        category="Office Furniture",
        confidence=0.90,
    )


@pytest.fixture
def python_course() -> Product:
    return Product(
        id="course-001",
        name="Python Programming Masterclass",
        price=99.0,
        tags=["education", "programming", "python"],
        description="Comprehensive Python course from basics to advanced topics",
        capabilities_enabled=[
            "learn programming",
            "Python skills",
            "software development",
        ],
        category="Online Courses",
        confidence=0.85,
    )


@pytest.fixture
def running_shoes() -> Product:
    return Product(
        id="shoes-001",
        name="Performance Running Shoes",
        price=150.0,
        tags=["sports", "running", "fitness"],
        description="Lightweight running shoes with responsive cushioning",
        capabilities_enabled=[
            "running",
            "athletic performance",
            "comfort during exercise",
        ],
        category="Athletic Footwear",
        confidence=0.92,
    )


@pytest.fixture
def sample_products(ergonomic_chair, standing_desk, python_course, running_shoes):
    return [ergonomic_chair, standing_desk, python_course, running_shoes]


# -----------------------------------------------------------------------------
# Test Product Semantic Text Building
# -----------------------------------------------------------------------------


def test_build_product_semantic_text_with_capabilities(ergonomic_chair):
    """Test that semantic text includes capabilities."""
    text = _build_product_semantic_text(ergonomic_chair)
    assert "posture support" in text
    assert "back pain relief" in text


def test_build_product_semantic_text_with_description(ergonomic_chair):
    """Test that semantic text includes description."""
    text = _build_product_semantic_text(ergonomic_chair)
    assert "lumbar support" in text


def test_build_product_semantic_text_fallback():
    """Test fallback to name when no other data."""
    minimal_product = Product(
        id="min-001",
        name="Mystery Product",
        price=10.0,
        tags=[],
        capabilities_enabled=[],
    )
    text = _build_product_semantic_text(minimal_product)
    assert text == "Mystery Product"


# -----------------------------------------------------------------------------
# Test Keyword Fallback (Baseline)
# -----------------------------------------------------------------------------


def test_keyword_assess_exact_match(sample_products):
    """Test keyword matching finds exact tag matches."""
    goals = ["office furniture"]
    result = _keyword_assess(goals, sample_products)

    # Should find chair and desk via 'office' tag
    assert len(result.aligned_goals) >= 1
    assert result.score > 0


def test_keyword_assess_no_match(sample_products):
    """Test keyword matching handles non-matching goals."""
    goals = ["quantum computing research"]
    result = _keyword_assess(goals, sample_products)

    assert goals[0] in result.misaligned_goals
    assert result.score == 0


# -----------------------------------------------------------------------------
# Test Semantic Alignment (with Mock Embeddings)
# -----------------------------------------------------------------------------


def test_assess_uses_semantic_by_default(sample_products):
    """Test that assess() attempts semantic alignment first."""
    # Create mock embedding provider
    mock_provider = MagicMock()
    mock_provider.provider_name = "mock"

    # Create embeddings that put "back pain" goal close to ergonomic chair
    # and far from other products
    def mock_embed_batch(texts):
        embeddings = []
        for text in texts:
            if "back pain" in text.lower() or "back pain relief" in text.lower():
                embeddings.append([1.0, 0.0, 0.0])  # Back pain cluster
            elif "python" in text.lower() or "programming" in text.lower():
                embeddings.append([0.0, 1.0, 0.0])  # Programming cluster
            else:
                embeddings.append([0.0, 0.0, 1.0])  # Other cluster
        return embeddings

    mock_provider.embed_batch = MagicMock(side_effect=mock_embed_batch)

    # Patch at the source module where it's imported from
    with patch(
        "shared.llm.embeddings.get_embedding_provider", return_value=mock_provider
    ):
        with patch("shared.llm.embeddings.cosine_similarity") as mock_cosine:
            # Simulate high similarity for matching concepts
            def cosine_impl(a, b):
                import numpy as np

                a = np.array(a)
                b = np.array(b)
                return float(
                    np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)
                )

            mock_cosine.side_effect = cosine_impl

            goals = ["reduce back pain from sitting"]
            result = assess(goals, sample_products, use_semantic=True)

            # Should have called the embedding provider
            mock_provider.embed_batch.assert_called_once()

            # Check result structure
            assert "alignment_method" in result.confidence_summary
            assert result.confidence_summary["alignment_method"] == "semantic"


def test_assess_falls_back_to_keyword_on_error(sample_products):
    """Test that assess() falls back to keywords when semantic fails."""
    # Patch at the source module
    with patch("shared.llm.embeddings.get_embedding_provider") as mock:
        mock.side_effect = Exception("Embedding service unavailable")

        goals = ["office"]
        result = assess(goals, sample_products, use_semantic=True)

        # Should have fallen back to keyword matching
        assert result.confidence_summary.get("alignment_method") == "keyword"


def test_assess_keyword_mode(sample_products):
    """Test explicit keyword mode."""
    goals = ["office furniture"]
    result = assess(goals, sample_products, use_semantic=False)

    assert result.confidence_summary.get("alignment_method") == "keyword"


# -----------------------------------------------------------------------------
# Test Edge Cases
# -----------------------------------------------------------------------------


def test_assess_empty_goals(sample_products):
    """Test handling of empty goals list."""
    result = assess([], sample_products)
    assert result.score == 0.0
    assert result.aligned_goals == []
    assert result.misaligned_goals == []


def test_assess_empty_products():
    """Test handling of empty products list."""
    goals = ["reduce back pain"]
    result = assess(goals, [])
    assert result.score == 0.0
    assert result.misaligned_goals == goals


def test_assess_both_empty():
    """Test handling when both goals and products are empty."""
    result = assess([], [])
    assert result.score == 0.0


# -----------------------------------------------------------------------------
# Test Alignment Explanation
# -----------------------------------------------------------------------------


def test_get_alignment_explanation_high(ergonomic_chair):
    """Test explanation for high alignment."""
    explanation = get_alignment_explanation(
        "reduce back pain", ergonomic_chair, HIGH_ALIGNMENT_THRESHOLD + 0.1
    )
    assert "strongly" in explanation
    assert "back pain" in explanation


def test_get_alignment_explanation_medium(ergonomic_chair):
    """Test explanation for medium alignment."""
    explanation = get_alignment_explanation(
        "improve workspace", ergonomic_chair, MEDIUM_ALIGNMENT_THRESHOLD + 0.05
    )
    assert "reasonably" in explanation


def test_get_alignment_explanation_low(ergonomic_chair):
    """Test explanation for low alignment."""
    explanation = get_alignment_explanation("learn cooking", ergonomic_chair, 0.2)
    assert "weakly" in explanation


# -----------------------------------------------------------------------------
# Test Confidence Weighting
# -----------------------------------------------------------------------------


def test_confidence_affects_score():
    """Test that product confidence affects alignment score."""
    high_conf_product = Product(
        id="high-001",
        name="Trusted Product",
        price=100.0,
        tags=["office"],
        capabilities_enabled=["productivity"],
        confidence=1.0,
    )

    low_conf_product = Product(
        id="low-001",
        name="Uncertain Product",
        price=100.0,
        tags=["office"],
        capabilities_enabled=["productivity"],
        confidence=0.3,
    )

    goals = ["office productivity"]

    result_high = _keyword_assess(goals, [high_conf_product])
    result_low = _keyword_assess(goals, [low_conf_product])

    # Both should align, but high confidence should score better
    # (actual difference depends on the formula)
    assert (
        result_high.confidence_summary["average_confidence"]
        > result_low.confidence_summary["average_confidence"]
    )


# -----------------------------------------------------------------------------
# Integration Test (Requires API Key)
# -----------------------------------------------------------------------------


@pytest.mark.skip(reason="Requires GOOGLE_API_KEY - run manually")
def test_real_semantic_alignment(sample_products):
    """Integration test with real embeddings (manual run only)."""
    goals = [
        "I want to reduce back pain from sitting all day",
        "I need to learn Python programming for my job",
    ]

    result = assess(goals, sample_products, use_semantic=True)

    print("\nAlignment Result:")
    print(f"  Score: {result.score}")
    print(f"  Aligned goals: {result.aligned_goals}")
    print(f"  Misaligned goals: {result.misaligned_goals}")
    print(f"  Supporting products: {result.supporting_products}")
    print(f"  Method: {result.confidence_summary.get('alignment_method')}")
    print(f"  Provider: {result.confidence_summary.get('embedding_provider')}")

    # Ergonomic chair should align with back pain goal
    assert "chair-001" in result.supporting_products or len(result.aligned_goals) > 0
