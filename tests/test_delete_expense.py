import importlib
import re
from datetime import date
from pathlib import Path

import pytest

from database import db

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
OTHER = {"name": "Other", "email": "other@spendly.com", "password": "other1234"}
ROOT = Path(__file__).resolve().parent.parent
TODAY = date.today().isoformat()
SCRIPT = "<script>alert(1)</script>"


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    import app as app_module

    importlib.reload(app_module)
    app_module.app.config["TESTING"] = True
    return app_module


@pytest.fixture
def client(app_module):
    return app_module.app.test_client()


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "helpers.db")
    db.init_db(path)
    db.seed_db(path)
    return path


def _login(client):
    return client.post("/login", data=DEMO)


def _demo_id(path=None):
    return db.get_user_by_email(DEMO["email"], path)["id"]


def _make_other_expense(path=None):
    """Create a second user with one expense; return (user_id, expense_id)."""
    user_id = db.create_user(OTHER["name"], OTHER["email"], OTHER["password"], path)
    expense_id = db.create_expense(user_id, 77.0, "Bills", TODAY, "Theirs", path)
    return user_id, expense_id


def _row(expense_id, path=None):
    conn = db.get_db(path)
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def _count(path=None):
    conn = db.get_db(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def _snapshot(path=None):
    conn = db.get_db(path)
    try:
        return [tuple(r) for r in conn.execute("SELECT * FROM expenses ORDER BY id")]
    finally:
        conn.close()


# ----------------------------------------------------------------- links --


def test_profile_rows_have_delete_links(client):
    _login(client)
    html = client.get("/profile?date_from=2000-01-01&date_to=2999-12-31").get_data(
        as_text=True
    )
    uid = _demo_id()
    for e in db.get_recent_expenses(uid, limit=None):
        pattern = (
            rf'<a class="expense-delete-link" href="/expenses/{e["id"]}/delete" '
            rf'aria-label="Delete {e["category"]} expense of ₹[^"]+ on [^"]+">Delete</a>'
        )
        assert re.search(pattern, html), e["id"]


def test_edit_page_links_to_delete(client):
    _login(client)
    html = client.get("/expenses/1/edit").get_data(as_text=True)
    assert 'href="/expenses/1/delete"' in html
    assert "Delete this expense" in html


# ------------------------------------------------------------ GET confirm --


def test_get_shows_confirmation(client):
    _login(client)
    response = client.get("/expenses/1/delete")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Delete expense?" in html
    assert "Food" in html
    assert "Lunch at cafe" in html
    assert "₹12.50" in html
    assert 'method="post"' in html
    assert 'action="/expenses/1/delete"' in html
    assert "Cancel" in html and 'href="/profile"' in html
    assert "This can't be undone." in html or "This can&#39;t be undone." in html


def test_get_shows_dash_for_null_description(client):
    _login(client)
    uid = _demo_id()
    eid = db.create_expense(uid, 5.0, "Other", TODAY, None)
    html = client.get(f"/expenses/{eid}/delete").get_data(as_text=True)
    assert "<dd>—</dd>" in html


def test_get_never_deletes(client):
    _login(client)
    before = _snapshot()
    for _ in range(3):
        assert client.get("/expenses/1/delete").status_code == 200
    assert _snapshot() == before


def test_confirmation_escapes_description(client):
    _login(client)
    eid = db.create_expense(_demo_id(), 5.0, "Other", TODAY, SCRIPT)
    html = client.get(f"/expenses/{eid}/delete").get_data(as_text=True)
    assert SCRIPT not in html
    assert "&lt;script&gt;" in html


# -------------------------------------------------------------- POST delete --


def test_post_deletes_only_that_row(client):
    _login(client)
    before = _snapshot()
    response = client.post("/expenses/1/delete")
    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"
    assert _row(1) is None
    assert _snapshot() == [r for r in before if r[0] != 1]


def test_flash_shows_once(client):
    _login(client)
    client.post("/expenses/1/delete")
    first = client.get("/profile").get_data(as_text=True)
    assert "Expense deleted." in first
    assert "Expense deleted." not in client.get("/profile").get_data(as_text=True)


def test_seeded_totals_after_delete(client):
    _login(client)
    uid = _demo_id()
    summary = db.get_expense_summary(uid)
    assert summary["count"] == 8
    assert round(summary["total"], 2) == 400.64
    client.post("/expenses/1/delete")
    summary = db.get_expense_summary(uid)
    assert summary["count"] == 7
    assert round(summary["total"], 2) == 388.14


def test_deleting_last_expense_shows_empty_state(client):
    _login(client)
    for eid in range(1, 9):
        assert client.post(f"/expenses/{eid}/delete").status_code == 302
    assert _count() == 0
    html = client.get("/profile").get_data(as_text=True)
    assert "No expenses yet" in html


def test_second_post_returns_404(client):
    _login(client)
    assert client.post("/expenses/1/delete").status_code == 302
    assert client.post("/expenses/1/delete").status_code == 404


# ------------------------------------------------------------------ access --


def test_logged_out_redirects_and_deletes_nothing(client):
    before = _snapshot()
    for method in (client.get, client.post):
        response = method("/expenses/1/delete")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
    assert _snapshot() == before


def test_stale_session_is_cleared(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.post("/expenses/1/delete")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
    assert _row(1) is not None


def test_missing_id_returns_404(client):
    _login(client)
    assert client.get("/expenses/9999/delete").status_code == 404
    assert client.post("/expenses/9999/delete").status_code == 404


def test_other_users_expense_returns_404_and_survives(client):
    _, other_eid = _make_other_expense()
    _login(client)
    before = tuple(_row(other_eid))
    assert client.get(f"/expenses/{other_eid}/delete").status_code == 404
    assert client.post(f"/expenses/{other_eid}/delete").status_code == 404
    assert tuple(_row(other_eid)) == before


def test_non_integer_id_returns_404(client):
    _login(client)
    assert client.get("/expenses/abc/delete").status_code == 404
    assert client.post("/expenses/abc/delete").status_code == 404


@pytest.mark.parametrize("method", ["put", "delete", "patch"])
def test_other_methods_return_405(client, method):
    _login(client)
    assert getattr(client, method)("/expenses/1/delete").status_code == 405
    assert _row(1) is not None


def test_form_tampering_is_ignored(client):
    other_uid, other_eid = _make_other_expense()
    _login(client)
    other_before = tuple(_row(other_eid))
    response = client.post(
        "/expenses/1/delete", data={"user_id": other_uid, "id": other_eid}
    )
    assert response.status_code == 302
    assert _row(1) is None
    assert tuple(_row(other_eid)) == other_before


# ---------------------------------------------------------------- db helper --


def test_delete_expense_by_id_owner(db_path):
    owner = _demo_id(db_path)
    before = _snapshot(db_path)
    assert db.delete_expense_by_id(1, owner, db_path) is True
    assert _row(1, db_path) is None
    assert _snapshot(db_path) == [r for r in before if r[0] != 1]


def test_delete_expense_by_id_not_owner_or_missing(db_path):
    other_uid, other_eid = _make_other_expense(db_path)
    owner = _demo_id(db_path)
    before = _snapshot(db_path)
    assert db.delete_expense_by_id(other_eid, owner, db_path) is False
    assert db.delete_expense_by_id(1, other_uid, db_path) is False
    assert db.delete_expense_by_id(9999, owner, db_path) is False
    assert _snapshot(db_path) == before


# ------------------------------------------------------------ static rules --


def test_files_follow_rules():
    templates = [
        (ROOT / "templates" / name).read_text()
        for name in ("delete_expense.html", "edit_expense.html", "profile.html")
    ]
    for text in templates:
        for banned in ('href="/', 'action="/', "<style", 'style="', "|safe"):
            assert banned not in text
    assert '{% extends "base.html" %}' in templates[0]
    for css in ("expense_form.css", "profile.css"):
        assert not re.search(
            r"#[0-9a-fA-F]{3,8}\b", (ROOT / "static" / "css" / css).read_text()
        )
    assert "coming in Step" not in (ROOT / "app.py").read_text()
