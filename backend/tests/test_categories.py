from alembic import command
from sqlalchemy import select

from due_brew import models


def test_migration_seeds_default_categories(alembic_cfg, db):
    command.downgrade(alembic_cfg, "0001")
    command.upgrade(alembic_cfg, "head")

    names = db.scalars(select(models.Category.name).order_by(models.Category.sort_order)).all()
    assert names[:4] == ["Produce", "Dairy", "Meat & Fish", "Bakery"]
    assert "Toiletries" in names and "Cleaning" in names


def test_create_and_list_sorted(as_user, alice):
    client = as_user(alice)
    client.post("/api/categories", json={"name": "Dairy", "sort_order": 2})
    client.post("/api/categories", json={"name": "Produce", "sort_order": 1})
    res = client.post("/api/categories", json={"name": "  Snacks  "})

    assert res.status_code == 201
    assert res.json()["name"] == "Snacks"
    assert res.json()["sort_order"] == 3  # appended after the current max
    assert [c["name"] for c in client.get("/api/categories").json()] == ["Produce", "Dairy", "Snacks"]


def test_duplicate_name_conflicts(as_user, alice, make_category):
    make_category("Dairy")

    assert as_user(alice).post("/api/categories", json={"name": "Dairy"}).status_code == 409


def test_rename_and_reorder(as_user, alice, make_category):
    dairy = make_category("Dairy")

    res = as_user(alice).patch(f"/api/categories/{dairy.id}", json={"name": "Dairy & Eggs", "sort_order": 9})

    assert res.json() == {"id": str(dairy.id), "name": "Dairy & Eggs", "sort_order": 9}


def test_rename_to_existing_name_conflicts(as_user, alice, make_category):
    make_category("Dairy")
    produce = make_category("Produce")

    assert as_user(alice).patch(f"/api/categories/{produce.id}", json={"name": "Dairy"}).status_code == 409


def test_delete_keeps_items_as_uncategorized(as_user, alice, make_category):
    client = as_user(alice)
    dairy = make_category("Dairy")
    item = client.post("/api/items", json={"name": "Milk", "category_id": str(dairy.id)}).json()

    assert client.delete(f"/api/categories/{dairy.id}").status_code == 204

    items = client.get("/api/items").json()
    assert [(i["id"], i["category_id"]) for i in items] == [(item["id"], None)]


def test_missing_category_404(as_user, alice):
    missing = "00000000-0000-0000-0000-000000000000"

    assert as_user(alice).patch(f"/api/categories/{missing}", json={"name": "x"}).status_code == 404
    assert as_user(alice).delete(f"/api/categories/{missing}").status_code == 404
