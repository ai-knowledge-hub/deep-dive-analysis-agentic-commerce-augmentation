from application.services.query_battery.audience_segmentation import (
    derive_segments_from_events,
)


def test_derive_segments_from_events_ready_to_buy_and_research():
    events = [
        {
            "event_type": "search",
            "metadata": {
                "session_id": "s1",
                "query": "best running shoes compare options",
                "actions": ["view_reviews", "compare_products"],
                "time_on_page": 180,
            },
        },
        {
            "event_type": "view_item",
            "metadata": {
                "session_id": "s1",
                "query": "running shoes review and fit",
                "actions": ["read_specs"],
                "time_on_page": 140,
            },
        },
        {
            "event_type": "search",
            "metadata": {
                "session_id": "s2",
                "query": "buy now in stock fast delivery running shoes",
                "actions": ["add_to_cart", "begin_checkout"],
                "time_on_page": 40,
            },
        },
        {
            "event_type": "purchase",
            "metadata": {
                "session_id": "s2",
                "actions": ["purchase_complete"],
            },
        },
    ]
    segments = derive_segments_from_events(events)
    labels = {item.label for item in segments}
    assert "Research-Heavy Comparers" in labels or "Urgent Ready-to-Buy" in labels
    assert len(segments) >= 1


def test_derive_segments_from_events_empty_input():
    assert derive_segments_from_events([]) == []
