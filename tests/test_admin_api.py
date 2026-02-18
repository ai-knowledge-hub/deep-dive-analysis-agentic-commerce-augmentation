from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient

if "google" not in sys.modules:
    google_pkg = types.ModuleType("google")
    genai_pkg = types.ModuleType("google.genai")
    genai_types_pkg = types.ModuleType("google.genai.types")
    genai_pkg.Client = lambda *args, **kwargs: None
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg

from shared.db.connection import init_db, set_database_path
from api.main import app
from shared.config.env import settings
from infrastructure.db.search.users import ensure_user


ADMIN_USER_ID = "admin-user"


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "admin-api.db"
    set_database_path(db_path)
    init_db()
    settings.admin_user_ids = ADMIN_USER_ID
    return TestClient(app)


def test_admin_client_brand_product_flow(client: TestClient):
    create_client = client.post(
        "/clients",
        json={"id": "client-1", "name": "Client One", "user_id": ADMIN_USER_ID},
    )
    assert create_client.status_code == 200
    assert create_client.json()["client"]["id"] == "client-1"

    list_clients = client.get(f"/clients?user_id={ADMIN_USER_ID}")
    assert list_clients.status_code == 200
    assert any(item["id"] == "client-1" for item in list_clients.json()["clients"])

    create_brand = client.post(
        "/clients/client-1/brands",
        json={"id": "brand-1", "name": "Brand One", "user_id": ADMIN_USER_ID},
    )
    assert create_brand.status_code == 200
    assert create_brand.json()["brand"]["client_id"] == "client-1"

    list_brands = client.get("/clients/client-1/brands?user_id=admin-user")
    assert list_brands.status_code == 200
    assert any(item["id"] == "brand-1" for item in list_brands.json()["brands"])

    create_product = client.post(
        "/brands/brand-1/products",
        json={"id": "prod-1", "name": "Product One", "user_id": ADMIN_USER_ID},
    )
    assert create_product.status_code == 200
    assert create_product.json()["product"]["brand_id"] == "brand-1"

    list_products = client.get("/brands/brand-1/products?user_id=admin-user")
    assert list_products.status_code == 200
    assert any(item["id"] == "prod-1" for item in list_products.json()["products"])


def test_admin_client_user_mapping(client: TestClient):
    client.post(
        "/clients",
        json={"id": "client-2", "name": "Client Two", "user_id": ADMIN_USER_ID},
    )
    ensure_user("user-xyz")
    add_user = client.post(
        "/clients/client-2/users",
        json={
            "member_user_id": "user-xyz",
            "role": "analyst",
            "user_id": ADMIN_USER_ID,
        },
    )
    assert add_user.status_code == 200
    assert add_user.json()["user"]["user_id"] == "user-xyz"

    list_users = client.get("/clients/client-2/users?user_id=admin-user")
    assert list_users.status_code == 200
    assert any(item["user_id"] == "user-xyz" for item in list_users.json()["users"])


def test_admin_skill_editing_and_history(client: TestClient):
    get_skill = client.get("/skills/signal_extractor?user_id=admin-user")
    assert get_skill.status_code == 200
    assert get_skill.json()["skill"]["name"] == "signal_extractor"

    updated = client.put(
        "/skills/signal_extractor",
        json={
            "name": "signal_extractor",
            "description": "Updated description",
            "version": "2026-02-02",
            "content": "Updated skill content",
            "enabled": True,
            "metadata": {"purpose": "signal_extraction"},
            "user_id": ADMIN_USER_ID,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["skill"]["version"] == "2026-02-02"

    history = client.get("/skills/signal_extractor/history?user_id=admin-user&limit=5")
    assert history.status_code == 200
    assert history.json()["history"]


def test_admin_canonical_spec_autofill_preview_and_apply(client: TestClient):
    client.post(
        "/clients",
        json={"id": "client-3", "name": "Client Three", "user_id": ADMIN_USER_ID},
    )
    client.post(
        "/clients/client-3/brands",
        json={"id": "brand-3", "name": "Brand Three", "user_id": ADMIN_USER_ID},
    )
    client.post(
        "/brands/brand-3/products",
        json={
            "id": "prod-3",
            "name": "Product Three",
            "description": "Lightstrike midsole, engineered mesh, 8.5mm drop, 240g",
            "metadata": {
                "ucp": {
                    "attributes": {"category": "running_shoes"},
                    "use_cases": ["daily_training"],
                }
            },
            "user_id": ADMIN_USER_ID,
        },
    )

    preview = client.post(
        "/brands/brand-3/products/prod-3/canonical-spec/autofill",
        json={"mode": "preview", "user_id": ADMIN_USER_ID},
    )
    assert preview.status_code == 200
    preview_spec = preview.json()["result"]["canonical_spec"]
    assert preview_spec["category"]

    apply = client.post(
        "/brands/brand-3/products/prod-3/canonical-spec/autofill",
        json={"mode": "apply", "user_id": ADMIN_USER_ID},
    )
    assert apply.status_code == 200
    product = apply.json()["result"]["product"]
    assert product
    metadata = product.get("metadata") or {}
    assert "canonical_intent_spec" in metadata
    assert "canonical_intent_spec_raw" in metadata


def test_admin_loop_maintenance_run_endpoint(client: TestClient):
    client.post(
        "/clients",
        json={"id": "client-maint", "name": "Client Maint", "user_id": ADMIN_USER_ID},
    )
    response = client.post(
        "/ops/loop-maintenance",
        json={
            "user_id": ADMIN_USER_ID,
            "client_id": "client-maint",
            "lookback_days": 30,
            "min_confidence": 0.7,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["client_id"] == "client-maint"
    assert "history" in payload
    assert isinstance(payload["history"], list)

    history_response = client.get(
        "/ops/loop-maintenance/history?client_id=client-maint&user_id=admin-user"
    )
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["runs"]
    assert history_payload["runs"][0]["client_id"] == "client-maint"
