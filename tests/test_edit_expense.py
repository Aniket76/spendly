import importlib
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from database import db

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
OTHER = {"name": "Other", "email": "other@spendly.com", "password": "other1234"}
ROOT = Path(__file__).resolve().parent.parent
TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
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


def _valid(**overrides):
    return {
        "amount": "99.99",
        "category": "Transport",
        "date": TODAY,
        "description": "Taxi home",
        **overrides,
    }


def _edit(client, expense_id=1, **overrides):
    return client.post(f"/expenses/{expense_id}/edit", data=_valid(**overrides))


# ---------------------------------------------------------------- access --


def test_logged_out_get_and_post_redirect_and_change_nothing(client):
    before = _row(1)
    for response in (client.get("/expenses/1/edit"), _edit(client)):
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
    assert tuple(_row(1)) == tuple(before)


def test_stale_session_is_cleared_and_redirected(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/expenses/1/edit")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_missing_expense_is_404(client):
    _login(client)
    assert client.get("/expenses/9999/edit").status_code == 404
    assert _edit(client, 9999).status_code == 404


def test_non_integer_id_is_404(client):
    _login(client)
    assert client.get("/expenses/abc/edit").status_code == 404


def test_other_users_expense_is_404_and_unchanged(client):
    _, other_id = _make_other_expense()
    before = tuple(_row(other_id))
    _login(client)
    assert client.get(f"/expenses/{other_id}/edit").status_code == 404
    assert _edit(client, other_id).status_code == 404
    # Ownership is checked before validation: invalid input is still 404.
    assert _edit(client, other_id, amount="abc").status_code == 404
    assert tuple(_row(other_id)) == before


# ------------------------------------------------------------------- GET --


def test_get_prefills_form(client):
    _login(client)
    response = client.get("/expenses/1/edit")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Edit expense" in html
    assert 'value="12.50"' in html
    assert re.search(r'<option value="Food" selected>', html)
    assert f'max="{TODAY}"' in html
    assert 'value="Lunch at cafe"' in html
    assert 'action="/expenses/1/edit"' in html


def test_get_with_null_description_is_empty(client):
    _login(client)
    # Seeded expense 7 ("Other", 15.00) has no description.
    html = client.get("/expenses/7/edit").get_data(as_text=True)
    assert re.search(r'name="description"[^>]*value=""', html, flags=re.S)


# ---------------------------------------------------------------- update --


def test_successful_update(client):
    _login(client)
    before_count = _count()
    response = _edit(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    assert "?" not in response.headers["Location"]
    row = _row(1)
    assert row["amount"] == 99.99
    assert row["category"] == "Transport"
    assert row["date"] == TODAY
    assert row["description"] == "Taxi home"
    assert row["user_id"] == _demo_id()
    assert _count() == before_count

    page = client.get("/profile").get_data(as_text=True)
    assert "Expense updated." in page
    assert "Taxi home" in page
    assert "Expense updated." not in client.get("/profile").get_data(as_text=True)


def test_totals_change_but_count_does_not(client):
    _login(client)
    assert _edit(client, amount="112.50", category="Food").status_code == 302
    page = client.get("/profile?range=all").get_data(as_text=True)
    assert "₹500.64" in page
    assert _count() == 8


def test_blank_description_stored_as_null(client):
    _login(client)
    _edit(client, description="   ")
    assert _row(1)["description"] is None
    page = client.get("/profile?range=all").get_data(as_text=True)
    assert 'data-label="Description">—</td>' in page


def test_unchanged_submit_still_redirects_with_flash(client):
    _login(client)
    before = tuple(_row(1))
    response = _edit(
        client,
        amount="12.50",
        category="Food",
        date=before[4],
        description="Lunch at cafe",
    )
    assert response.status_code == 302
    assert tuple(_row(1)) == before
    assert "Expense updated." in client.get("/profile").get_data(as_text=True)


# ------------------------------------------------------------ validation --


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": ""},
        {"amount": "abc"},
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "12.345"},
        {"amount": "1e309"},
        {"amount": "nan"},
        {"amount": "10000000.01"},
        {"category": ""},
        {"category": "Rent"},
        {"date": ""},
        {"date": "2026-13-40"},
        {"date": "2026-1-5"},
        {"date": TOMORROW},
        {"description": "x" * 201},
    ],
)
def test_invalid_input_returns_400_and_changes_nothing(client, overrides):
    _login(client)
    before = tuple(_row(1))
    response = _edit(client, **overrides)
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert 'role="alert"' in html
    assert tuple(_row(1)) == before


def test_invalid_input_preserves_other_values(client):
    _login(client)
    html = _edit(client, amount="abc", description="Keep me").get_data(as_text=True)
    assert 'value="abc"' in html
    assert 'value="Keep me"' in html
    assert '<option value="Transport" selected>' in html


# ------------------------------------------------------------- tampering --


def test_body_user_id_and_id_are_ignored(client):
    other_user, other_id = _make_other_expense()
    other_before = tuple(_row(other_id))
    _login(client)
    response = client.post(
        "/expenses/1/edit",
        data=_valid(user_id=str(other_user), id=str(other_id)),
    )
    assert response.status_code == 302
    assert _row(1)["user_id"] == _demo_id()
    assert _row(1)["amount"] == 99.99
    assert tuple(_row(other_id)) == other_before


def test_script_description_is_escaped(client):
    _login(client)
    _edit(client, description=SCRIPT)
    assert _row(1)["description"] == SCRIPT
    form = client.get("/expenses/1/edit").get_data(as_text=True)
    page = client.get("/profile?range=all").get_data(as_text=True)
    for html in (form, page):
        assert SCRIPT not in html
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------- profile links --


def test_every_profile_row_has_edit_link(client):
    _login(client)
    page = client.get("/profile?range=all").get_data(as_text=True)
    ids = [row["id"] for row in db.get_recent_expenses(_demo_id(), limit=None)]
    assert len(ids) == 8
    for expense_id in ids:
        link = re.search(
            rf'<a class="expense-edit-link" href="/expenses/{expense_id}/edit"'
            r' aria-label="Edit [^"]+ expense of ₹[^"]+ on [^"]+">Edit</a>',
            page,
        )
        assert link, expense_id
    assert 'scope="col"><span class="sr-only">Actions</span>' in page


def test_delete_stub_unchanged(client):
    assert b"coming in Step 9" in client.get("/expenses/1/delete").data


# ------------------------------------------------------------- db helpers --


def test_get_expense_by_id_is_owner_scoped(db_path):
    owner = _demo_id(db_path)
    other_user, _ = _make_other_expense(db_path)
    row = db.get_expense_by_id(1, owner, db_path)
    assert row["category"] == "Food"
    assert db.get_expense_by_id(1, other_user, db_path) is None
    assert db.get_expense_by_id(9999, owner, db_path) is None


def test_update_expense_changes_only_target_row(db_path):
    owner = _demo_id(db_path)
    before_other = tuple(_row(2, db_path))
    before = _row(1, db_path)
    assert db.update_expense(1, owner, 10.456, "Bills", TODAY, " Note ", db_path)
    after = _row(1, db_path)
    assert after["amount"] == 10.46
    assert after["category"] == "Bills"
    assert after["date"] == TODAY
    assert after["description"] == "Note"
    assert after["user_id"] == before["user_id"]
    assert after["created_at"] == before["created_at"]
    assert tuple(_row(2, db_path)) == before_other


def test_update_expense_blank_description_is_null(db_path):
    owner = _demo_id(db_path)
    assert db.update_expense(1, owner, 5, "Food", TODAY, "  ", db_path)
    assert _row(1, db_path)["description"] is None


def test_update_expense_rejects_other_user(db_path):
    other_user, _ = _make_other_expense(db_path)
    before = tuple(_row(1, db_path))
    assert db.update_expense(1, other_user, 1, "Food", TODAY, "x", db_path) is False
    assert tuple(_row(1, db_path)) == before
    assert db.update_expense(9999, other_user, 1, "Food", TODAY, "x", db_path) is False


# ------------------------------------------------------- static rules --


def test_new_files_follow_rules():
    template = (ROOT / "templates" / "edit_expense.html").read_text()
    css = (ROOT / "static" / "css" / "profile.css").read_text()
    profile = (ROOT / "templates" / "profile.html").read_text()
    for html in (template, profile):
        for banned in ('href="/', 'action="/', "<style", 'style="', "|safe"):
            assert banned not in html
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert '{% extends "base.html" %}' in template
