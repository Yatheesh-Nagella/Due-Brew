def _add(client, name, **fields):
    return client.post("/api/items", json={"name": name, **fields}).json()


def _shape(grocery):
    return [(g["label"], [(i["name"], i["status"]) for i in g["items"]]) for g in grocery["groups"]]


def test_grouped_by_category_need_before_low(as_user, alice, make_category):
    client = as_user(alice)
    produce = make_category("Produce", 1)
    dairy = make_category("Dairy", 2)
    _add(client, "Yogurt", category_id=str(dairy.id), status="low")
    _add(client, "Milk", category_id=str(dairy.id))
    _add(client, "Butter", category_id=str(dairy.id), status="low")
    _add(client, "Bananas", category_id=str(produce.id))
    _add(client, "Sponges")
    _add(client, "Cheese", category_id=str(dairy.id), status="have")  # not on the list

    grocery = client.get("/api/grocery-list").json()

    assert _shape(grocery) == [
        ("Produce", [("Bananas", "needed")]),
        ("Dairy", [("Milk", "needed"), ("Butter", "low"), ("Yogurt", "low")]),
        ("Uncategorized", [("Sponges", "needed")]),
    ]
    assert grocery["groups"][1]["key"] == str(dairy.id)
    assert grocery["groups"][2]["key"] is None
    assert (grocery["need_count"], grocery["low_count"]) == (3, 2)


def test_grouped_by_store(as_user, alice):
    client = as_user(alice)
    _add(client, "Rice", store="Costco", status="low")
    _add(client, "Paper towels", store="costco")
    _add(client, "Milk", store="Aldi")
    _add(client, "Bread")

    grocery = client.get("/api/grocery-list", params={"group_by": "store"}).json()

    assert [g["label"].lower() for g in grocery["groups"]] == ["aldi", "costco", "any store"]
    # Store names match ignoring case; Need still comes before Low.
    assert [i["name"] for i in grocery["groups"][1]["items"]] == ["Paper towels", "Rice"]
    assert grocery["groups"][2]["key"] is None


def test_bought_removes_from_list(as_user, alice):
    client = as_user(alice)
    milk = _add(client, "Milk")
    _add(client, "Bread")

    client.post(f"/api/items/{milk['id']}/bought")

    assert _shape(client.get("/api/grocery-list").json()) == [("Uncategorized", [("Bread", "needed")])]


def test_empty_list(as_user, alice):
    assert as_user(alice).get("/api/grocery-list").json() == {"need_count": 0, "low_count": 0, "groups": []}


def test_bad_group_by_rejected(as_user, alice):
    assert as_user(alice).get("/api/grocery-list", params={"group_by": "color"}).status_code == 422
