from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from shared.db.connection import init_db, set_database_path
from api.main import app
from shared.config.env import settings
from infrastructure.db.users import ensure_user


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
