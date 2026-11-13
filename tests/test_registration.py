import importlib
import re
import sqlite3
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash

import database.db as db

VALID = {"name": "Test User", "email": "test@example.com", "password": "password123"}


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


def _count_users():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def _post(client, **overrides):
    return client.post("/register", data={**VALID, **overrides})


# ------------------------------------------------------------------ routes


def test_get_register_returns_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    for field in (b'name="name"', b'name="email"', b'name="password"'):
        assert field in response.data


def test_register_success_redirects_to_login(client):
    response = _post(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_register_stores_lowercased_email_and_hash(client):
    before = _count_users()
    _post(client, email="  MixedCase@Example.COM ")
    assert _count_users() == before + 1
    user = db.get_user_by_email("mixedcase@example.com")
    assert user is not None
    assert user["email"] == "mixedcase@example.com"
    assert user["password_hash"] != VALID["password"]
    assert check_password_hash(user["password_hash"], VALID["password"])


def test_register_duplicate_email_rejected(client):
    before = _count_users()
    response = _post(client, email="DEMO@spendly.com")
    assert response.status_code == 400
    assert b"already exists" in response.data
    assert _count_users() == before


def test_register_short_password_rejected(client):
    before = _count_users()
    response = _post(client, password="1234567")
    assert b"at least 8 characters" in response.data
    assert _count_users() == before


@pytest.mark.parametrize("field", ["name", "email"])
def test_register_blank_fields_rejected(client, field):
    before = _count_users()
    response = _post(client, **{field: "   "})
    assert b"All fields are required" in response.data
    assert _count_users() == before


@pytest.mark.parametrize("email", ["foo", "foo@bar", "foo@.", "@bar.com"])
def test_register_invalid_email_rejected(client, email):
    before = _count_users()
    response = _post(client, email=email)
    assert b"valid email" in response.data
    assert _count_users() == before


def test_register_error_repopulates_name_and_email(client):
    response = _post(client, password="short")
    html = response.data.decode()
    assert 'value="Test User"' in html
    assert 'value="test@example.com"' in html
    password_input = re.search(r'<input[^>]*name="password"[^>]*>', html).group(0)
    assert "value=" not in password_input


def test_register_form_uses_url_for_action(client):
    template = Path("templates/register.html").read_text()
    assert 'action="/register"' not in template
    assert "url_for('register')" in template
    assert b'action="/register"' in client.get("/register").data


# ------------------------------------------------------------------ db helpers


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "helpers.db")
    db.init_db(path)
    return path


def test_create_user_returns_id_and_hashes(db_path):
    user_id = db.create_user("A", "A@Example.com", "password123", db_path)
    user = db.get_user_by_email("a@example.com", db_path)
    assert user["id"] == user_id
    assert check_password_hash(user["password_hash"], "password123")


def test_get_user_by_email_case_insensitive_and_missing(db_path):
    db.create_user("A", "a@example.com", "password123", db_path)
    assert db.get_user_by_email("A@EXAMPLE.COM", db_path) is not None
    assert db.get_user_by_email("nobody@example.com", db_path) is None


def test_create_user_duplicate_email_raises(db_path):
    db.create_user("A", "a@example.com", "password123", db_path)
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("B", "A@example.com", "password456", db_path)
