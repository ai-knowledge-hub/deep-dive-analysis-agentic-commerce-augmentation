"""Seed a full demo tenant with realistic overview/dashboard data.

Creates an "Acme Sports" client with products, batteries, experiments,
simulations, validations, and beliefs for rich charts.
Safe to re-run: clears prior demo data by client id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from shared.db.connection import DEFAULT_DB_PATH, get_connection, init_db
from infrastructure.db.core.json import to_json

CLIENT_ID = "client-acme"
CLIENT_NAME = "Acme Sports"
BRANDS = [
    {"id": "brand-acme-run", "name": "Acme Run"},
    {"id": "brand-acme-trail", "name": "Acme Trail"},
    {"id": "brand-acme-active", "name": "Acme Active"},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dt(days_ago: int, hours: int = 0) -> str:
    return (_now() - timedelta(days=days_ago, hours=hours)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _upsert_client(*, client_id: str, name: str, metadata: Dict[str, Any]) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO clients (id, name, metadata_json)
        VALUES (?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            metadata_json = excluded.metadata_json
        """,
        (client_id, name, to_json(metadata) or to_json({})),
    )


def _upsert_brand(*, brand_id: str, name: str) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO brands (id, client_id, name, metadata_json)
        VALUES (?, ?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            client_id = excluded.client_id,
            name = excluded.name,
            metadata_json = excluded.metadata_json
        """,
        (brand_id, CLIENT_ID, name, to_json({})),
    )


def _upsert_product(
    *,
    product_id: str,
    brand_id: str,
    name: str,
    description: str,
    metadata: Dict[str, Any],
) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO products (id, brand_id, name, description, metadata_json)
        VALUES (?, ?, ?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            brand_id = excluded.brand_id,
            name = excluded.name,
            description = excluded.description,
            metadata_json = excluded.metadata_json
        """,
        (product_id, brand_id, name, description, to_json(metadata) or to_json({})),
    )


def _clear_demo_data() -> None:
    conn = get_connection()
    conn.execute("DELETE FROM replay_records WHERE client_id = ?", (CLIENT_ID,))
    conn.execute("DELETE FROM simulation_lessons WHERE client_id = ?", (CLIENT_ID,))
    conn.execute("DELETE FROM simulation_runs WHERE client_id = ?", (CLIENT_ID,))
    conn.execute("DELETE FROM experiment_validations WHERE client_id = ?", (CLIENT_ID,))
    conn.execute(
        "DELETE FROM experiment_calibrations WHERE client_id = ?", (CLIENT_ID,)
    )
    conn.execute("DELETE FROM analytics_events WHERE client_id = ?", (CLIENT_ID,))
    conn.execute("DELETE FROM audience_archetypes WHERE client_id = ?", (CLIENT_ID,))
    conn.execute("DELETE FROM brand_beliefs WHERE client_id = ?", (CLIENT_ID,))
    conn.execute("DELETE FROM query_batteries WHERE client_id = ?", (CLIENT_ID,))
    conn.execute("DELETE FROM clients WHERE id = ?", (CLIENT_ID,))
    conn.commit()


def _canonical_spec(
    category: str, sub_category: str, features: List[str], uses: List[str]
):
    return {
        "domain_vertical": "sports_retail",
        "category": category,
        "sub_category": sub_category,
        "top_use_cases": uses[:3],
        "core_constraints": ["budget_mid", "durability", "comfort"],
        "target_archetypes": [
            "marathon_trainer",
            "weekend_runner",
            "injury_prevention",
        ],
        "must_not_target": ["fashion_only", "elite_racer_only"],
        "features": features,
        "use_cases": uses,
    }


def _seed_products() -> List[Dict[str, Any]]:
    products = [
        {
            "id": "acme-velocity-road",
            "brand_id": "brand-acme-run",
            "name": "Velocity Road Trainer",
            "description": "Responsive daily trainer with breathable mesh and stable heel platform.",
            "category": "running_shoes",
            "sub": "road",
            "features": [
                "responsive cushioning",
                "breathable upper",
                "stable heel",
                "moderate drop",
            ],
            "uses": ["daily training", "long-distance running", "injury prevention"],
        },
        {
            "id": "acme-pace-lite",
            "brand_id": "brand-acme-run",
            "name": "Pace Lite Racer",
            "description": "Lightweight speed shoe for tempo runs and race day performance.",
            "category": "running_shoes",
            "sub": "race",
            "features": ["lightweight", "snappy toe-off", "race-ready fit"],
            "uses": ["tempo workouts", "race day", "speed training"],
        },
        {
            "id": "acme-trail-grip",
            "brand_id": "brand-acme-trail",
            "name": "TrailGrip Terrain",
            "description": "Trail runner with aggressive lugs and protective toe guard.",
            "category": "running_shoes",
            "sub": "trail",
            "features": ["aggressive traction", "toe protection", "durable outsole"],
            "uses": ["trail running", "rocky terrain", "wet conditions"],
        },
        {
            "id": "acme-stability-guide",
            "brand_id": "brand-acme-run",
            "name": "Stability Guide",
            "description": "Guided stability shoe designed to keep your stride aligned.",
            "category": "running_shoes",
            "sub": "stability",
            "features": ["supportive arch", "guided stability", "cushioned ride"],
            "uses": ["overpronation support", "injury prevention", "daily training"],
        },
        {
            "id": "acme-rain-shell",
            "brand_id": "brand-acme-active",
            "name": "StormShield Shell",
            "description": "Water-resistant running shell with breathable venting.",
            "category": "sports_apparel",
            "sub": "outerwear",
            "features": ["water-resistant", "wind protection", "lightweight packable"],
            "uses": ["rainy runs", "windy conditions", "layering"],
        },
        {
            "id": "acme-warm-vest",
            "brand_id": "brand-acme-active",
            "name": "CoreWarm Vest",
            "description": "Insulated vest for cool-weather mileage.",
            "category": "sports_apparel",
            "sub": "vest",
            "features": ["insulated core", "breathable panels", "easy layering"],
            "uses": ["cold morning runs", "layering", "wind protection"],
        },
        {
            "id": "acme-compression-tight",
            "brand_id": "brand-acme-active",
            "name": "Endurance Tight",
            "description": "Compression tight for muscle support and recovery.",
            "category": "sports_apparel",
            "sub": "bottoms",
            "features": ["compression support", "moisture wicking", "mobility stretch"],
            "uses": ["long training runs", "recovery", "cold weather"],
        },
        {
            "id": "acme-speed-short",
            "brand_id": "brand-acme-active",
            "name": "SpeedStride Short",
            "description": "Lightweight running short with secure storage.",
            "category": "sports_apparel",
            "sub": "shorts",
            "features": ["lightweight fabric", "secure pockets", "quick dry"],
            "uses": ["summer runs", "race day", "daily training"],
        },
    ]

    for product in products:
        metadata = {
            "display_name": product["name"],
            "canonical_intent_spec": _canonical_spec(
                product["category"],
                product["sub"],
                product["features"],
                product["uses"],
            ),
        }
        _upsert_product(
            product_id=product["id"],
            brand_id=product["brand_id"],
            name=product["name"],
            description=product["description"],
            metadata=metadata,
        )
    return products


def _seed_audience_archetypes() -> None:
    archetypes = [
        ("marathon_trainer", "Trains for distance, values cushioning and recovery."),
        ("weekend_runner", "Runs 2-3x weekly, wants comfort and durability."),
        ("injury_prevention", "Prioritizes stability and joint support."),
        ("trail_explorer", "Runs off-road, needs traction and protection."),
        ("speed_chaser", "Focuses on tempo and racing performance."),
        ("budget_focused", "Wants value and dependable basics."),
    ]
    conn = get_connection()
    for label, desc in archetypes:
        archetype_id = f"acme-archetype-{label}"
        conn.execute(
            """
            INSERT INTO audience_archetypes
                (id, client_id, brand_id, domain_vertical, label, description, archetype_json, source, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, json(?), ?, json(?), ?, ?)
            """,
            (
                archetype_id,
                CLIENT_ID,
                "brand-acme-run",
                "sports_retail",
                label,
                desc,
                to_json({"label": label, "description": desc}),
                "demo_seed",
                to_json({"confidence": 0.78}),
                _dt(60),
                _dt(60),
            ),
        )


def _seed_query_batteries(products: List[Dict[str, Any]]) -> Dict[str, str]:
    conn = get_connection()
    batteries = [
        (
            "battery-road",
            "Road shoes baseline",
            "road training coverage",
            "bottom_up",
            45,
        ),
        (
            "battery-trail",
            "Trail shoes baseline",
            "trail intent coverage",
            "bottom_up",
            38,
        ),
        (
            "battery-apparel",
            "Apparel coverage",
            "outerwear + base layers",
            "bottom_up",
            30,
        ),
    ]
    battery_map: Dict[str, str] = {}
    for key, name, purpose, mode, days_ago in batteries:
        battery_id = f"acme-{key}"
        product_id = products[0]["id"]
        conn.execute(
            """
            INSERT INTO query_batteries
                (id, client_id, brand_id, product_id, name, purpose, generation_mode, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                battery_id,
                CLIENT_ID,
                "brand-acme-run",
                product_id,
                name,
                purpose,
                mode,
                "active",
                _dt(days_ago),
            ),
        )
        battery_map[key] = battery_id

    queries = [
        (
            "battery-road",
            "best running shoes for daily training",
            "intent",
            "daily_runner",
        ),
        (
            "battery-road",
            "stable running shoes for long distance",
            "intent",
            "injury_prevention",
        ),
        (
            "battery-road",
            "lightweight running shoes for speed workouts",
            "intent",
            "speed_chaser",
        ),
        (
            "battery-road",
            "comfortable road running shoes for beginners",
            "intent",
            "weekend_runner",
        ),
        (
            "battery-road",
            "cushioned running shoes for marathon training",
            "intent",
            "marathon_trainer",
        ),
        (
            "battery-trail",
            "trail running shoes with aggressive grip",
            "intent",
            "trail_explorer",
        ),
        (
            "battery-trail",
            "best trail shoes for rocky terrain",
            "intent",
            "trail_explorer",
        ),
        ("battery-trail", "lightweight trail running shoes", "intent", "speed_chaser"),
        (
            "battery-trail",
            "trail shoes with toe protection",
            "intent",
            "trail_explorer",
        ),
        (
            "battery-apparel",
            "water resistant running jacket",
            "intent",
            "weekend_runner",
        ),
        (
            "battery-apparel",
            "insulated running vest for cold weather",
            "intent",
            "marathon_trainer",
        ),
        (
            "battery-apparel",
            "compression tights for long runs",
            "intent",
            "injury_prevention",
        ),
        (
            "battery-apparel",
            "lightweight running shorts with pockets",
            "intent",
            "speed_chaser",
        ),
    ]
    for idx, (key, text, qtype, archetype) in enumerate(queries, start=1):
        conn.execute(
            """
            INSERT INTO query_battery_queries
                (id, battery_id, query_text, query_type, intent_archetype, constraints_json, weight, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, json(?), ?, ?, ?)
            """,
            (
                f"acme-q-{idx}",
                battery_map[key],
                text,
                qtype,
                archetype,
                to_json({}),
                1.0,
                1,
                _dt(35 - (idx % 7)),
            ),
        )
    return battery_map


def _seed_experiments(
    products: List[Dict[str, Any]], battery_map: Dict[str, str]
) -> None:
    conn = get_connection()
    experiments = [
        (
            "exp-road-framing",
            "Outcome framing test",
            products[0]["id"],
            "battery-road",
            28,
        ),
        (
            "exp-trail-grip",
            "Trail grip emphasis",
            products[2]["id"],
            "battery-trail",
            24,
        ),
        (
            "exp-stability",
            "Stability language test",
            products[3]["id"],
            "battery-road",
            20,
        ),
        (
            "exp-vest-copy",
            "Outerwear copy test",
            products[4]["id"],
            "battery-apparel",
            16,
        ),
        (
            "exp-compression",
            "Compression benefits test",
            products[6]["id"],
            "battery-apparel",
            12,
        ),
        ("exp-speed", "Speed benefits test", products[1]["id"], "battery-road", 9),
    ]
    for exp_id, name, product_id, battery_key, days_ago in experiments:
        conn.execute(
            """
            INSERT INTO experiments
                (id, client_id, brand_id, product_id, battery_id, name, hypothesis_json, competitor_policy_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, json(?), json(?), ?, ?)
            """,
            (
                exp_id,
                CLIENT_ID,
                "brand-acme-run",
                product_id,
                battery_map[battery_key],
                name,
                to_json({"metric": "win_rate", "direction": "increase"}),
                to_json({}),
                "completed",
                _dt(days_ago),
            ),
        )
        variants = [
            (f"{exp_id}-control", "Control", "copy"),
            (f"{exp_id}-outcome", "Outcome Focused", "copy"),
            (f"{exp_id}-spec", "Spec Focused", "copy"),
        ]
        for variant_id, label, vtype in variants:
            conn.execute(
                """
                INSERT INTO experiment_variants
                    (id, experiment_id, label, type, payload_json, created_at)
                VALUES (?, ?, ?, ?, json(?), ?)
                """,
                (
                    variant_id,
                    exp_id,
                    label,
                    vtype,
                    to_json({"version": label}),
                    _dt(days_ago),
                ),
            )
        metrics = [
            (f"{exp_id}-control", 0.42, 0.51),
            (f"{exp_id}-outcome", 0.68, 0.63),
            (f"{exp_id}-spec", 0.55, 0.58),
        ]
        for idx, (variant_id, win_rate, avg_score) in enumerate(metrics):
            conn.execute(
                """
                INSERT INTO experiment_metrics
                    (id, experiment_id, variant_id, metrics_json, created_at)
                VALUES (?, ?, ?, json(?), ?)
                """,
                (
                    str(uuid.uuid4()),
                    exp_id,
                    variant_id,
                    to_json(
                        {
                            "win_rate": win_rate + (idx * 0.02),
                            "avg_score": avg_score + (idx * 0.01),
                            "avg_protocol_readiness_score": 78 + idx,
                        }
                    ),
                    _dt(days_ago - 1),
                ),
            )
        conn.execute(
            """
            INSERT INTO experiment_recommendations
                (id, experiment_id, recommendation_json, created_at)
            VALUES (?, ?, json(?), ?)
            """,
            (
                str(uuid.uuid4()),
                exp_id,
                to_json(
                    {
                        "action": "create_variant",
                        "reason": "Reduce spec density for comparison queries",
                    }
                ),
                _dt(days_ago - 1),
            ),
        )


def _seed_validations() -> None:
    conn = get_connection()
    for idx in range(20):
        conn.execute(
            """
            INSERT INTO experiment_validations
                (id, experiment_id, variant_id, client_id, brand_id, product_id, platform, query_text, observed_products_json, observed_winner_variant_id, observed_position, notes, is_correct, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, json(?), ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                "exp-road-framing",
                "exp-road-framing-outcome",
                CLIENT_ID,
                "brand-acme-run",
                "acme-velocity-road",
                "chatgpt",
                "best running shoes for daily training",
                to_json(["acme-velocity-road", "acme-stability-guide"]),
                "exp-road-framing-outcome",
                1,
                "Demo validation",
                1 if idx % 5 != 0 else 0,
                _dt(25 - idx),
            ),
        )


def _seed_simulations(products: List[Dict[str, Any]]) -> None:
    conn = get_connection()
    for idx in range(45):
        product = products[idx % len(products)]
        run_id = f"acme-sim-{idx}"
        lift = 0.08 + (idx % 6) * 0.03
        result = {
            "lift_summary": {
                "delta_points": round(lift * 100, 2),
                "optimized_product_id": product["id"],
            },
            "gap_analysis": [
                {
                    "product_id": product["id"],
                    "missing_signals": ["durability", "fit"]
                    if idx % 2 == 0
                    else ["comfort"],
                    "winner_signals": ["stability", "cushioning"],
                    "competitor_summary": "Competitors stress durability and fit.",
                }
            ],
            "protocol_readiness": [
                {
                    "product_id": product["id"],
                    "protocol": "ucp",
                    "issues": [
                        {
                            "field": "ucp_readiness_score",
                            "message": "78 / 100",
                        }
                    ],
                }
            ],
        }
        conn.execute(
            """
            INSERT INTO simulation_runs
                (id, user_id, session_id, client_id, brand_id, product_id, query, scenario_json, products_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                None,
                None,
                CLIENT_ID,
                product["brand_id"],
                product["id"],
                "running shoes for daily training",
                to_json({"query": "running shoes for daily training"}),
                to_json([{"id": product["id"], "name": product["name"]}]),
                to_json(result),
                _dt(60 - idx),
            ),
        )
        if idx % 4 == 0:
            conn.execute(
                """
                INSERT INTO simulation_lessons
                    (run_id, user_id, client_id, lesson, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    None,
                    CLIENT_ID,
                    "Outcome framing improved long-run intent alignment.",
                    _dt(60 - idx),
                ),
            )


def _seed_beliefs() -> None:
    conn = get_connection()
    for idx in range(10):
        conn.execute(
            """
            INSERT INTO brand_beliefs
                (id, client_id, brand_id, product_id, hypothesis_json, evidence_json, recommendation, confidence, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, json(?), json(?), ?, ?, json(?), ?, ?)
            """,
            (
                str(uuid.uuid4()),
                CLIENT_ID,
                "brand-acme-run",
                "acme-velocity-road",
                to_json({"hypothesis": "Outcome framing improves discovery."}),
                to_json({"win_rate_lift": 0.2}),
                "Emphasize cushioning and injury prevention.",
                0.78,
                to_json({"source": "demo_seed"}),
                _dt(50 - idx * 3),
                _dt(50 - idx * 3),
            ),
        )


def _seed_replay_records() -> None:
    conn = get_connection()
    for idx in range(12):
        conn.execute(
            """
            INSERT INTO replay_records
                (id, run_type, entity_type, entity_id, user_id, client_id, session_id, record_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                "evidence.analyze",
                "evidence_flow",
                f"demo-{idx}",
                None,
                CLIENT_ID,
                None,
                to_json({"outputs": {"count": 5 + (idx % 3)}}),
                _dt(40 - idx * 2),
            ),
        )


def seed_demo_acme() -> Dict[str, int]:
    init_db()
    _clear_demo_data()

    _upsert_client(
        client_id=CLIENT_ID,
        name=CLIENT_NAME,
        metadata={"is_demo": True, "vertical": "sports_retail"},
    )
    for brand in BRANDS:
        _upsert_brand(brand_id=brand["id"], name=brand["name"])

    products = _seed_products()
    _seed_audience_archetypes()
    battery_map = _seed_query_batteries(products)
    _seed_experiments(products, battery_map)
    _seed_validations()
    _seed_simulations(products)
    _seed_beliefs()
    _seed_replay_records()

    get_connection().commit()
    return {
        "clients": 1,
        "brands": len(BRANDS),
        "products": len(products),
        "batteries": len(battery_map),
    }


if __name__ == "__main__":
    seeded = seed_demo_acme()
    print(f"Seeded demo client in {DEFAULT_DB_PATH}: {seeded}")
