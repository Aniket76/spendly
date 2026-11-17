import importlib
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pytest

from database import db

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
ROOT = Path(__file__).resolve().parent.parent
TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


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


def _expense_rows(path=None):
    conn = db.get_db(path)
    try:
        return conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()
    finally:
        conn.close()


def _valid(**overrides):
    return {
        "amount": "250.50",
        "category": "Food",
        "date": TODAY,
        "description": "Dinner",
        **overrides,
    }


def _post(client, **overrides):
    return client.post("/expenses/add", data=_valid(**overrides))


# ---------------------------------------------------------------- access --


def test_logged_out_get_redirects_to_login(client):
    response = client.get("/expenses/add")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logged_out_post_redirects_and_inserts_nothing(client):
    before = len(_expense_rows())
    response = _post(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert len(_expense_rows()) == before


def test_stale_session_is_cleared_and_redirected(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/expenses/add")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


# ------------------------------------------------------------------- GET --


def test_get_renders_form_with_defaults(client):
    _login(client)
    response = client.get("/expenses/add")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'value="{TODAY}"' in html
    assert f'max="{TODAY}"' in html
    assert "Choose a category" in html
    for label in ("Amount", "Category", "Date", "Description"):
        assert label in html
    for category in (
        "Food",
        "Transport",
        "Bills",
        "Health",
        "Entertainment",
        "Shopping",
        "Other",
    ):
        assert f'<option value="{category}"' in html


# --------------------------------------------------------------- success --


def test_valid_post_inserts_and_redirects_with_flash(client):
    _login(client)
    before = len(_expense_rows())
    response = _post(client)
    assert response.status_code == 302
    location = urlparse(response.headers["Location"])
    assert location.path == "/profile"
    assert location.query == ""  # no filter, so the default Last 7 days applies

    rows = _expense_rows()
    assert len(rows) == before + 1
    row = rows[-1]
    assert row["user_id"] == _demo_id()
    assert row["amount"] == 250.50
    assert row["category"] == "Food"
    assert row["date"] == TODAY
    assert row["description"] == "Dinner"

    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Expense added." in page
    assert "Dinner" in page
    # The flash is shown once only.
    assert "Expense added." not in client.get("/profile").get_data(as_text=True)


def test_seeded_totals_change_after_adding(client):
    _login(client)
    before = client.get("/profile?range=all").get_data(as_text=True)
    assert "₹400.64" in before
    _post(client, amount="100.00", description="Extra")
    after = client.get("/profile?range=all").get_data(as_text=True)
    assert "₹500.64" in after
    assert re.search(r'stat-label">Expenses</p>\s*<p class="stat-value">9<', after)


def test_redirect_opens_on_last_7_days_with_new_expense_listed(client):
    _login(client)
    response = _post(client, description="Fresh lunch")
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Fresh lunch" in page
    chip = re.search(r'<a class="filter-preset"[^>]*>Last 7 days</a>', page)
    assert chip and 'aria-current="true"' in chip.group(0)
    assert (
        f'name="date_from" value="{(date.today() - timedelta(days=6)).isoformat()}"'
        in page
    )


def test_expense_older_than_7_days_is_saved_but_not_in_default_view(client):
    _login(client)
    response = _post(client, date="2020-01-15", description="Ancient lunch")
    assert response.status_code == 302
    default_view = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Ancient lunch" not in default_view
    all_time = client.get("/profile?range=all").get_data(as_text=True)
    assert "Ancient lunch" in all_time


def test_blank_description_stored_as_null(client):
    _login(client)
    _post(client, description="   ")
    assert _expense_rows()[-1]["description"] is None


def test_description_script_tag_is_escaped(client):
    _login(client)
    _post(client, description="<script>alert(1)</script>")
    assert _expense_rows()[-1]["description"] == "<script>alert(1)</script>"
    page = client.get("/profile?range=all").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_forged_user_id_is_ignored(client, app_module):
    other_id = db.create_user("Other", "other@example.com", "password123")
    _login(client)
    _post(client, user_id=str(other_id))
    assert _expense_rows()[-1]["user_id"] == _demo_id()
    assert db.get_expense_summary(other_id)["count"] == 0


# ------------------------------------------------------------ validation --


INVALID_CASES = [
    ("missing_amount", {"amount": ""}),
    ("text_amount", {"amount": "abc"}),
    ("zero_amount", {"amount": "0"}),
    ("negative_amount", {"amount": "-5"}),
    ("three_decimals", {"amount": "12.345"}),
    ("overflow_amount", {"amount": "1e309"}),
    ("nan_amount", {"amount": "nan"}),
    ("inf_amount", {"amount": "inf"}),
    ("too_large_amount", {"amount": "10000000.01"}),
    ("missing_category", {"category": ""}),
    ("unknown_category", {"category": "Rent"}),
    ("missing_date", {"date": ""}),
    ("impossible_date", {"date": "2026-13-40"}),
    ("unpadded_date", {"date": "2026-1-5"}),
    ("future_date", {"date": TOMORROW}),
    ("long_description", {"description": "x" * 201}),
]


@pytest.mark.parametrize(
    "overrides", [c[1] for c in INVALID_CASES], ids=[c[0] for c in INVALID_CASES]
)
def test_invalid_input_returns_400_and_inserts_nothing(client, overrides):
    _login(client)
    before = len(_expense_rows())
    response = _post(client, **overrides)
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert 'role="alert"' in html
    assert len(_expense_rows()) == before


def test_invalid_input_preserves_other_values(client):
    _login(client)
    response = _post(client, amount="abc", description="Keep me", category="Bills")
    html = response.get_data(as_text=True)
    assert 'value="Keep me"' in html
    assert re.search(r'<option value="Bills" selected>', html)
    assert f'value="{TODAY}"' in html


def test_boundary_values_are_accepted(client):
    _login(client)
    assert _post(client, amount="10000000").status_code == 302
    assert _post(client, amount="0.01", description="x" * 200).status_code == 302
    assert _post(client, date=TODAY).status_code == 302


# ---------------------------------------------------------------- the FAB --


def _fab(html):
    return re.search(r'<a class="fab"[^>]*>', html)


def test_fab_present_with_data(client):
    _login(client)
    tag = _fab(client.get("/profile?range=all").get_data(as_text=True))
    assert tag
    assert 'href="/expenses/add"' in tag.group(0)
    assert 'aria-label="Add expense"' in tag.group(0)


def test_fab_present_when_range_has_no_matches(client):
    _login(client)
    html = client.get("/profile?date_from=2001-01-01&date_to=2001-01-02").get_data(
        as_text=True
    )
    assert "No expenses in this range" in html
    assert _fab(html)


def test_fab_present_for_user_with_no_expenses(client):
    db.create_user("New Person", "new@example.com", "password123")
    client.post("/login", data={"email": "new@example.com", "password": "password123"})
    html = client.get("/profile").get_data(as_text=True)
    assert "No expenses yet" in html
    assert "Use the + button" in html
    assert _fab(html)


def test_fab_on_home_page_when_logged_in(client):
    _login(client)
    html = client.get("/").get_data(as_text=True)
    tag = _fab(html)
    assert tag
    assert 'href="/expenses/add"' in tag.group(0)
    assert 'aria-label="Add expense"' in tag.group(0)
    assert 'class="has-fab"' in html


def test_fab_absent_on_home_page_when_logged_out(client):
    html = client.get("/").get_data(as_text=True)
    assert not _fab(html)
    assert "has-fab" not in html


def test_fab_absent_on_other_pages_when_logged_in(client):
    _login(client)
    for path in ("/expenses/add", "/terms-and-conditions", "/privacy-policy"):
        html = client.get(path).get_data(as_text=True)
        assert not _fab(html), path


def test_fab_absent_on_login_and_register_when_logged_out(client):
    for path in ("/login", "/register"):
        assert not _fab(client.get(path).get_data(as_text=True)), path


def test_blank_description_renders_dash_on_profile(client):
    _login(client)
    _post(client, description="", amount="77.77")
    page = client.get("/profile?range=all").get_data(as_text=True)
    rows = re.findall(r"<tr>.*?</tr>", page, flags=re.S)
    row = next(r for r in rows if "₹77.77" in r)
    assert 'data-label="Description">—</td>' in row


# ------------------------------------------------------------- DB helper --


def test_create_expense_returns_id_and_stores_row(db_path):
    uid = _demo_id(db_path)
    new_id = db.create_expense(uid, 19.999, "Food", TODAY, "  Snack  ", db_path)
    row = next(r for r in _expense_rows(db_path) if r["id"] == new_id)
    assert row["amount"] == 20.0
    assert row["description"] == "Snack"
    assert row["user_id"] == uid


def test_create_expense_blank_description_is_null(db_path):
    uid = _demo_id(db_path)
    db.create_expense(uid, 5, "Other", TODAY, "   ", db_path)
    db.create_expense(uid, 5, "Other", TODAY, None, db_path)
    assert [r["description"] for r in _expense_rows(db_path)[-2:]] == [None, None]


def test_create_expense_rejects_unknown_user(db_path):
    before = len(_expense_rows(db_path))
    with pytest.raises(sqlite3.IntegrityError):
        db.create_expense(9999, 5, "Food", TODAY, None, db_path)
    assert len(_expense_rows(db_path)) == before


def test_create_expense_treats_sql_text_as_data(db_path):
    uid = _demo_id(db_path)
    payload = "x'); DROP TABLE expenses; --"
    db.create_expense(uid, 5, "Food", TODAY, payload, db_path)
    assert _expense_rows(db_path)[-1]["description"] == payload


# ------------------------------------------------------- other guarantees --


def test_other_stubs_unchanged(client):
    # Edit is implemented in Step 7; logged out it redirects to login.
    response = client.get("/expenses/1/edit")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    delete = client.get("/expenses/1/delete")
    assert delete.status_code == 302
    assert delete.headers["Location"].endswith("/login")


def test_new_templates_and_css_follow_rules():
    template = (ROOT / "templates" / "add_expense.html").read_text()
    profile = (ROOT / "templates" / "profile.html").read_text()
    for text in (template, profile):
        for banned in ('href="/', 'action="/', "<style", 'style="', "|safe"):
            assert banned not in text
    for name in ("expense_form.css", "profile.css"):
        css = (ROOT / "static" / "css" / name).read_text()
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
