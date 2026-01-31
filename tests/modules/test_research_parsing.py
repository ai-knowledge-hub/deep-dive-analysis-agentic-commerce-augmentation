from __future__ import annotations

from domain.conversation import research as research_domain


def test_build_insights_parses_json_products():
    response = """
    {
      "products": [
        {
          "name": "ASICS Gel-Excite 8 Men's Running Shoes",
          "price": 55,
          "source_url": "https://www.amazon.co.uk/dp/B09J5K7V5L",
          "summary": "Dark navy road shoe with moderate support."
        }
      ],
      "notes": ["Prices observed Nov 2024"]
    }
    """
    insights = research_domain.build_insights(
        response=response,
        confidence=0.42,
        query="dark running shoes",
        goals=["Support flat feet"],
        tool_outputs=[],
    )

    assert len(insights) == 1
    assert insights[0]["title"].startswith("ASICS Gel-Excite 8")
    assert insights[0]["url"].startswith("https://www.amazon.co.uk")


def test_build_insights_reconstructs_from_scaffold_lines():
    response = """
    {
      "products": [
        {
          "name": "New Balance 608v5 Men's Walking/Running Shoes",
          "price": 45,
          "source_url": "https://www.amazon.co.uk/dp/B07P8V7J9L",
          "summary": "Dark grey stability shoe with reinforced heel."
        }
      ]
    }
    """
    # Simulate line-split JSON output
    insights = research_domain.build_insights(
        response=response.replace(",", ",\n"),
        confidence=0.35,
        query="dark stability shoes",
        goals=["Flat-foot support"],
        tool_outputs=[],
    )

    assert len(insights) == 1
    assert "New Balance 608v5" in insights[0]["title"]
    assert insights[0]["url"].endswith("B07P8V7J9L")
