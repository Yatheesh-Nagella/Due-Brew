"""get_current_user: the only place identity headers are read."""

LOGIN = "Tailscale-User-Login"


def test_me_returns_the_housemate_matching_the_header(client, make_user, env):
    env(APP_ENV="production")
    alice = make_user(tailscale_login="alice@example.com", display_name="Alice")
    make_user(tailscale_login="bob@example.com", display_name="Bob")

    res = client.get("/api/me", headers={LOGIN: "alice@example.com"})

    assert res.status_code == 200
    assert res.json()["id"] == str(alice.id)
    assert res.json()["display_name"] == "Alice"


def test_each_housemate_gets_themselves(client, make_user, env):
    env(APP_ENV="production")
    make_user(tailscale_login="alice@example.com", display_name="Alice")
    make_user(tailscale_login="bob@example.com", display_name="Bob")

    assert client.get("/api/me", headers={LOGIN: "bob@example.com"}).json()["display_name"] == "Bob"
    assert client.get("/api/me", headers={LOGIN: "alice@example.com"}).json()["display_name"] == "Alice"


def test_missing_header_is_rejected_in_production(client, make_user, env):
    env(APP_ENV="production")
    make_user()

    assert client.get("/api/me").status_code == 401


def test_unknown_login_gets_403(client, make_user, env):
    env(APP_ENV="production")
    make_user(tailscale_login="alice@example.com")

    assert client.get("/api/me", headers={LOGIN: "stranger@example.com"}).status_code == 403


def test_dev_user_login_ignored_in_production(client, make_user, env):
    make_user(tailscale_login="alice@example.com")
    env(APP_ENV="production", DEV_USER_LOGIN="alice@example.com")

    assert client.get("/api/me").status_code == 401


def test_unset_app_env_counts_as_production(client, make_user, env):
    make_user(tailscale_login="alice@example.com")
    env(APP_ENV=None, DEV_USER_LOGIN="alice@example.com")

    assert client.get("/api/me").status_code == 401


def test_dev_user_login_used_in_development(client, make_user, env):
    make_user(tailscale_login="alice@example.com", display_name="Alice")
    env(APP_ENV="development", DEV_USER_LOGIN="alice@example.com")

    res = client.get("/api/me")

    assert res.status_code == 200
    assert res.json()["display_name"] == "Alice"


def test_header_wins_over_dev_user_login(client, make_user, env):
    make_user(tailscale_login="alice@example.com", display_name="Alice")
    make_user(tailscale_login="bob@example.com", display_name="Bob")
    env(APP_ENV="development", DEV_USER_LOGIN="alice@example.com")

    assert client.get("/api/me", headers={LOGIN: "bob@example.com"}).json()["display_name"] == "Bob"


def test_dependency_override_is_how_tests_act_as_a_user(as_user, make_user):
    bob = make_user(display_name="Bob")

    assert as_user(bob).get("/api/me").json()["display_name"] == "Bob"
