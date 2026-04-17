from __future__ import annotations

import importlib
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    db_path = tmp_path / "financeiro_categorization_test.db"
    upload_dir = tmp_path / "uploads"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))

    sys.modules.pop("backend.app", None)
    module = importlib.import_module("backend.app")
    module = importlib.reload(module)

    yield module

    sys.modules.pop("backend.app", None)


@pytest.fixture()
def client(app_module):
    return TestClient(app_module.app)


def seed_transaction(app_module, *, description, category_id=None, source=None):
    session = app_module.SessionLocal()
    try:
        tx = app_module.Transaction(
            import_file_id=None,
            account_id="account-1",
            date=date(2025, 7, 10),
            description=description,
            amount=Decimal("12.50"),
            type="debit",
            category_id=category_id,
            categorized_at=app_module.utc_now() if category_id is not None else None,
            categorization_source=source,
            hash=app_module.compute_hash(
                date(2025, 7, 10),
                description,
                Decimal("12.50"),
            ),
            raw_data={"seeded": True},
            created_at=app_module.utc_now(),
            updated_at=app_module.utc_now(),
        )
        session.add(tx)
        session.commit()
        session.refresh(tx)
        return tx.id
    finally:
        session.close()


def test_category_crud_and_system_protection(client):
    list_response = client.get("/api/v1/categories")
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] >= 1
    assert any(item["name"] == "Uncategorized" for item in body["data"])

    create_response = client.post(
        "/api/v1/categories",
        json={"name": "Groceries", "color": "#10B981", "icon": "shopping-cart"},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Groceries"
    assert created["color"] == "#10B981"
    assert created["icon"] == "shopping-cart"
    assert created["is_system"] is False

    dup_response = client.post(
        "/api/v1/categories",
        json={"name": "gRoCeRiEs"},
    )
    assert dup_response.status_code == 409
    assert dup_response.json()["detail"]["code"] == "CATEGORY_ALREADY_EXISTS"

    update_response = client.put(
        f"/api/v1/categories/{created['id']}",
        json={"name": "Food", "color": "#123456"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Food"
    assert updated["color"] == "#123456"

    delete_response = client.delete(f"/api/v1/categories/{created['id']}")
    assert delete_response.status_code == 204

    system_category_id = next(
        item["id"] for item in body["data"] if item["name"] == "Uncategorized"
    )
    protected_delete = client.delete(f"/api/v1/categories/{system_category_id}")
    assert protected_delete.status_code == 403
    assert protected_delete.json()["detail"]["code"] == "SYSTEM_CATEGORY_PROTECTED"


def test_rule_crud_and_duplicate_guard(client):
    category_response = client.post(
        "/api/v1/categories",
        json={"name": "Transport", "color": "#0EA5E9"},
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]

    rule_response = client.post(
        "/api/v1/rules",
        json={
            "keyword": "uber trip",
            "category_id": category_id,
            "match_type": "contains",
            "priority": 50,
        },
    )
    assert rule_response.status_code == 201
    rule = rule_response.json()
    assert rule["keyword"] == "uber trip"
    assert rule["category_id"] == category_id
    assert rule["match_type"] == "contains"
    assert rule["priority"] == 50
    assert rule["source"] == "manual"

    dup_rule_response = client.post(
        "/api/v1/rules",
        json={
            "keyword": "UBER TRIP",
            "category_id": category_id,
            "match_type": "contains",
        },
    )
    assert dup_rule_response.status_code == 409
    assert dup_rule_response.json()["detail"]["code"] == "RULE_ALREADY_EXISTS"

    update_rule_response = client.put(
        f"/api/v1/rules/{rule['id']}",
        json={
            "keyword": "uber",
            "match_type": "starts_with",
            "priority": 60,
            "is_active": False,
        },
    )
    assert update_rule_response.status_code == 200
    updated = update_rule_response.json()
    assert updated["keyword"] == "uber"
    assert updated["match_type"] == "starts_with"
    assert updated["priority"] == 60
    assert updated["is_active"] is False

    delete_rule_response = client.delete(f"/api/v1/rules/{rule['id']}")
    assert delete_rule_response.status_code == 204


def test_categorize_transaction_learns_rule(client, app_module):
    category_response = client.post(
        "/api/v1/categories",
        json={"name": "Groceries", "color": "#22C55E"},
    )
    assert category_response.status_code == 201
    category = category_response.json()

    transaction_id = seed_transaction(
        app_module,
        description="Pão de Açúcar",
        category_id=None,
        source=None,
    )

    response = client.post(
        f"/api/v1/transactions/{transaction_id}/categorize",
        json={"category_id": category["id"], "learn_rule": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transaction_id"] == transaction_id
    assert body["category_id"] == category["id"]
    assert body["category_name"] == "Groceries"
    assert body["categorization_source"] == "manual"
    assert body["learned_rule"] is not None
    assert body["learned_rule"]["keyword"] == "pao de acucar"
    assert body["learned_rule"]["match_type"] == "contains"
    assert body["learned_rule"]["source"] == "learned"

    rules_response = client.get("/api/v1/rules?search=pao%20de%20acucar")
    assert rules_response.status_code == 200
    rules = rules_response.json()
    assert rules["total"] == 1


def test_bulk_categorize_updates_many(client, app_module):
    category_response = client.post(
        "/api/v1/categories",
        json={"name": "Utilities", "color": "#6366F1"},
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]

    tx1 = seed_transaction(app_module, description="Light bill")
    tx2 = seed_transaction(app_module, description="Water bill")
    tx3 = seed_transaction(app_module, description="Internet bill")

    response = client.post(
        "/api/v1/transactions/categorize-bulk",
        json={"transaction_ids": [tx1, tx2, tx3], "category_id": category_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["updated_count"] == 3
    assert body["category_id"] == category_id
    assert body["category_name"] == "Utilities"

    session = app_module.SessionLocal()
    try:
        rows = (
            session.query(app_module.Transaction)
            .filter(app_module.Transaction.id.in_([tx1, tx2, tx3]))
            .all()
        )
        assert len(rows) == 3
        assert all(row.category_id == category_id for row in rows)
        assert all(row.categorization_source == "bulk" for row in rows)
    finally:
        session.close()


def test_run_categorization_matches_rule_and_preserves_manual(client, app_module):
    grocery_response = client.post(
        "/api/v1/categories",
        json={"name": "Groceries", "color": "#10B981"},
    )
    assert grocery_response.status_code == 201
    grocery_id = grocery_response.json()["id"]

    other_response = client.post(
        "/api/v1/categories",
        json={"name": "Other", "color": "#A855F7"},
    )
    assert other_response.status_code == 201
    other_id = other_response.json()["id"]

    rule_response = client.post(
        "/api/v1/rules",
        json={
            "keyword": "supermercado extra",
            "category_id": grocery_id,
            "match_type": "contains",
            "priority": 50,
        },
    )
    assert rule_response.status_code == 201

    auto_tx = seed_transaction(app_module, description="Compra no Supermercado Extra")
    manual_tx = seed_transaction(
        app_module,
        description="Compra no Supermercado Extra",
        category_id=other_id,
        source="manual",
    )

    response = client.post(
        "/api/v1/categorize/run",
        json={"scope": "all", "account_id": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["processed"] == 1
    assert body["categorized"] == 1
    assert body["uncategorized"] == 0
    assert "duration_ms" in body

    session = app_module.SessionLocal()
    try:
        auto_row = session.get(app_module.Transaction, auto_tx)
        manual_row = session.get(app_module.Transaction, manual_tx)

        assert auto_row is not None
        assert manual_row is not None

        assert auto_row.category_id == grocery_id
        assert auto_row.categorization_source == "auto"

        assert manual_row.category_id == other_id
        assert manual_row.categorization_source == "manual"
    finally:
        session.close()


def test_delete_category_clears_transactions_and_rules(client, app_module):
    category_response = client.post(
        "/api/v1/categories",
        json={"name": "Fuel", "color": "#F97316"},
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]

    rule_response = client.post(
        "/api/v1/rules",
        json={
            "keyword": "posto",
            "category_id": category_id,
            "match_type": "contains",
        },
    )
    assert rule_response.status_code == 201

    tx_id = seed_transaction(
        app_module,
        description="Posto Ipiranga",
        category_id=category_id,
        source="manual",
    )

    delete_response = client.delete(f"/api/v1/categories/{category_id}")
    assert delete_response.status_code == 204

    session = app_module.SessionLocal()
    try:
        tx = session.get(app_module.Transaction, tx_id)
        assert tx is not None
        assert tx.category_id is None

        rule = (
            session.query(app_module.CategorizationRule)
            .filter_by(id=rule_response.json()["id"])
            .first()
        )
        assert rule is None
    finally:
        session.close()


def test_list_transactions_returns_items(client, app_module):
    category_response = client.post(
        "/api/v1/categories",
        json={"name": "Groceries", "color": "#10B981"},
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]

    tx_id = seed_transaction(
        app_module,
        description="Supermercado Extra",
        category_id=category_id,
        source="manual",
    )

    response = client.get("/api/v1/transactions")
    assert response.status_code == 200

    body = response.json()
    assert body["pagination"]["total_items"] >= 1
    assert len(body["items"]) >= 1

    item = next(row for row in body["items"] if row["id"] == tx_id)
    assert item["description"] == "Supermercado Extra"
    assert item["category_id"] == category_id
    assert item["category_name"] == "Groceries"
    assert item["account_id"] == "account-1"


def test_patch_transaction_category_updates_only_category(client, app_module):
    old_category_response = client.post(
        "/api/v1/categories",
        json={"name": "Old", "color": "#A3A3A3"},
    )
    assert old_category_response.status_code == 201
    old_category_id = old_category_response.json()["id"]

    new_category_response = client.post(
        "/api/v1/categories",
        json={"name": "New", "color": "#22C55E"},
    )
    assert new_category_response.status_code == 201
    new_category_id = new_category_response.json()["id"]

    tx_id = seed_transaction(
        app_module,
        description="Taxi Ride",
        category_id=old_category_id,
        source="manual",
    )

    response = client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"category_id": new_category_id},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == tx_id
    assert body["description"] == "Taxi Ride"
    assert body["category_id"] == new_category_id
    assert body["category_name"] == "New"
    assert body["categorization_source"] == "manual"

    session = app_module.SessionLocal()
    try:
        tx = session.get(app_module.Transaction, tx_id)
        assert tx is not None
        assert tx.description == "Taxi Ride"
        assert tx.category_id == new_category_id
        assert tx.categorization_source == "manual"
    finally:
        session.close()
