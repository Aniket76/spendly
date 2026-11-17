import importlib
import re
from pathlib import Path

import pytest

import database.db as db

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
ERROR = b"Invalid email or password."


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client backed by a temp DB; the real expense_tracker.db is never used."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    import app as app_module

    importlib.reload(app_module)  # re-run import-time init/seed on the temp DB
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _login(client, **overrides):
    return client.post("/login", data={**DEMO, **overrides})


def _session_user_id(client):
    with client.session_transaction() as sess:
        return sess.get("user_id")


def _demo_id():
    return db.get_user_by_email(DEMO["email"])["id"]


# ------------------------------------------------------------------ login page


def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b'name="email"' in response.data
    assert b'name="password"' in response.data


def test_login_template_has_no_hardcoded_action():
    source = Path("templates/login.html").read_text()
    assert 'action="/login"' not in source
    assert "url_for('login')" in source


# ------------------------------------------------------------------ success


def test_valid_login_redirects_and_sets_session(client):
    response = _login(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"
    assert _session_user_id(client) == _demo_id()


def test_email_case_and_whitespace_insensitive(client):
    response = _login(client, email="  DEMO@Spendly.com ")
    assert response.status_code == 302
    assert _session_user_id(client) == _demo_id()


def test_registered_user_can_login(client):
    client.post(
        "/register",
        data={"name": "New", "email": "new@example.com", "password": "password123"},
    )
    response = _login(client, email="new@example.com", password="password123")
    assert response.status_code == 302
    assert _session_user_id(client) is not None


def test_session_holds_only_user_id(client):
    _login(client)
    with client.session_transaction() as sess:
        assert dict(sess) == {"user_id": _demo_id()}


# ------------------------------------------------------------------ failures


def test_wrong_password_shows_error_no_session(client):
    response = _login(client, password="wrong-password")
    assert response.status_code == 400
    assert ERROR in response.data
    assert _session_user_id(client) is None


def test_unknown_email_same_error_as_wrong_password(client):
    response = _login(client, email="nobody@example.com")
    assert response.status_code == 400
    assert ERROR in response.data
    assert _session_user_id(client) is None


@pytest.mark.parametrize("field", ["email", "password"])
def test_blank_fields_show_error_no_session(client, field):
    response = _login(client, **{field: ""})
    assert response.status_code == 400
    assert ERROR in response.data
    assert _session_user_id(client) is None


def test_email_repopulated_password_not(client):
    response = _login(client, password="wrong-password")
    html = response.data.decode()
    assert 'value="demo@spendly.com"' in html
    password_input = re.search(r'<input[^>]*name="password"[^>]*>', html).group(0)
    assert "value=" not in password_input
    assert "wrong-password" not in html


# ------------------------------------------------------------------ navbar


def test_navbar_logged_in_vs_out(client):
    out = client.get("/").data
    assert b"Sign in" in out and b"Get started" in out
    assert b"Sign out" not in out

    _login(client)
    in_ = client.get("/").data
    assert b"Sign out" in in_
    assert b"Get started" not in in_ and b"Sign in" not in in_


# ------------------------------------------------------------------ redirects


def test_login_page_redirects_when_logged_in(client):
    _login(client)
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"


def test_logout_clears_session_and_redirects(client):
    _login(client)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert _session_user_id(client) is None
    assert b"Get started" in client.get("/").data


def test_logout_when_logged_out_ok(client):
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_stub_routes_unchanged(client):
    # /expenses/add is implemented in Step 6; see tests/test_add_expense.py.
    # /expenses/<id>/edit is implemented in Step 7; logged out it redirects.
    response = client.get("/expenses/1/edit")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    delete = client.get("/expenses/1/delete")
    assert delete.status_code == 302
    assert delete.headers["Location"].endswith("/login")
