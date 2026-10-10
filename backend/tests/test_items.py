from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from due_brew.api.main import app

MISSING = "00000000-0000-0000-0000-000000000000"


def test_quick_add_creates_a_needed_item(as_user, alice):
    res = as_user(alice).post("/api/items", json={"name": "  Oat milk "})

    assert res.status_code == 201
    item = res.json()
    assert item["name"] == "Oat milk"
    assert item["status"] == "needed"
    assert item["category"] is None and item["quantity"] is None
    assert item["added_by_user"]["display_name"] == "Alice"
    assert item["updated_by_user"]["display_name"] == "Alice"


def test_create_with_all_fields(as_user, alice, make_category):
    dairy = make_category("Dairy")
    body = {
        "name": "Eggs",
        "category_id": str(dairy.id),
        "quantity": 12,
        "unit": "ct",
        "status": "low",
        "store": "Costco",
        "notes": "free range",
    }

    item = as_user(alice).post("/api/items", json=body).json()

    assert item["category"]["name"] == "Dairy"
    assert item["quantity"] == 12
    assert (item["unit"], item["status"], item["store"], item["notes"]) == (
        "ct",
        "low",
        "Costco",
        "free range",
    )


def test_blank_name_rejected(as_user, alice):
    assert as_user(alice).post("/api/items", json={"name": "   "}).status_code == 422


def test_unknown_category_rejected(as_user, alice):
    assert as_user(alice).post("/api/items", json={"name": "x", "category_id": MISSING}).status_code == 422


def test_negative_quantity_rejected(as_user, alice):
    assert as_user(alice).post("/api/items", json={"name": "x", "quantity": -1}).status_code == 422


# --- duplicate guard ---


def test_duplicate_name_flips_existing_back_to_needed(as_user, alice, bob):
    milk = as_user(alice).post("/api/items", json={"name": "Milk"}).json()
    as_user(alice).post(f"/api/items/{milk['id']}/bought")

    res = as_user(bob).post("/api/items", json={"name": "mILK "})

    assert res.status_code == 200
    assert res.json()["id"] == milk["id"]
    assert res.json()["name"] == "Milk"  # keeps the original spelling
    assert res.json()["status"] == "needed"
    assert res.json()["added_by_user"]["display_name"] == "Alice"
    assert res.json()["updated_by_user"]["display_name"] == "Bob"
    assert len(as_user(bob).get("/api/items").json()) == 1


def test_duplicate_of_low_item_becomes_needed(as_user, alice):
    client = as_user(alice)
    client.post("/api/items", json={"name": "Rice", "status": "low"})

    assert client.post("/api/items", json={"name": "rice"}).json()["status"] == "needed"


def test_concurrent_quick_adds_make_one_row(as_user, alice):
    as_user(alice)  # installs the identity override for the threads' clients too

    def add(_):
        return TestClient(app).post("/api/items", json={"name": "Bananas"}).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(add, range(8)))

    assert sorted(codes) == [200] * 7 + [201]
    assert len(as_user(alice).get("/api/items").json()) == 1


def test_rename_onto_existing_name_conflicts(as_user, alice):
    client = as_user(alice)
    client.post("/api/items", json={"name": "Milk"})
    bread = client.post("/api/items", json={"name": "Bread"}).json()

    assert client.patch(f"/api/items/{bread['id']}", json={"name": "MILK"}).status_code == 409


# --- edit / status ---


def test_patch_changes_only_sent_fields_and_records_editor(as_user, alice, bob, make_category):
    produce = make_category("Produce")
    item = as_user(alice).post("/api/items", json={"name": "Apples", "store": "Aldi", "quantity": 3}).json()

    res = as_user(bob).patch(
        f"/api/items/{item['id']}", json={"category_id": str(produce.id), "store": None, "unit": "lb"}
    )

    updated = res.json()
    assert updated["category"]["name"] == "Produce"
    assert updated["store"] is None
    assert updated["unit"] == "lb"
    assert updated["quantity"] == 3
    assert updated["added_by_user"]["display_name"] == "Alice"
    assert updated["updated_by_user"]["display_name"] == "Bob"


def test_patch_rejects_clearing_required_fields(as_user, alice):
    item = as_user(alice).post("/api/items", json={"name": "Apples"}).json()

    assert as_user(alice).patch(f"/api/items/{item['id']}", json={"name": None}).status_code == 422
    assert as_user(alice).patch(f"/api/items/{item['id']}", json={"status": None}).status_code == 422


def test_bought_and_add_to_list(as_user, alice, bob):
    item = as_user(alice).post("/api/items", json={"name": "Coffee"}).json()

    bought = as_user(bob).post(f"/api/items/{item['id']}/bought").json()
    assert (bought["status"], bought["updated_by_user"]["display_name"]) == ("have", "Bob")

    back = as_user(alice).post(f"/api/items/{item['id']}/add-to-list").json()
    assert (back["status"], back["updated_by_user"]["display_name"]) == ("needed", "Alice")


def test_delete(as_user, alice):
    client = as_user(alice)
    item = client.post("/api/items", json={"name": "Coffee"}).json()

    assert client.delete(f"/api/items/{item['id']}").status_code == 204
    assert client.get("/api/items").json() == []
    assert client.delete(f"/api/items/{item['id']}").status_code == 404


def test_missing_item_404(as_user, alice):
    client = as_user(alice)
    assert client.patch(f"/api/items/{MISSING}", json={"name": "x"}).status_code == 404
    assert client.post(f"/api/items/{MISSING}/bought").status_code == 404
    assert client.post(f"/api/items/{MISSING}/add-to-list").status_code == 404


# --- listing ---


def test_list_filters_by_status_and_category(as_user, alice, make_category):
    client = as_user(alice)
    dairy = make_category("Dairy", 1)
    client.post("/api/items", json={"name": "Milk", "category_id": str(dairy.id)})
    client.post("/api/items", json={"name": "Cheese", "category_id": str(dairy.id), "status": "have"})
    client.post("/api/items", json={"name": "Soap", "status": "have"})

    def names(**params):
        return [i["name"] for i in client.get("/api/items", params=params).json()]

    assert names() == ["Cheese", "Milk", "Soap"]  # by category, uncategorized last
    assert names(status="have") == ["Cheese", "Soap"]
    assert names(category_id=str(dairy.id)) == ["Cheese", "Milk"]
    assert names(category_id=str(dairy.id), status="needed") == ["Milk"]
    assert client.get("/api/items", params={"status": "gone"}).status_code == 422
