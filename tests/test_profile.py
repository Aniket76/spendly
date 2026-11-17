import importlib
import re
from datetime import date
from pathlib import Path

import pytest

import database.db as db

DEMO = {"email": "demo@spendly.com", "password": "demo123"}


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


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "helpers.db")
    db.init_db(path)
    db.seed_db(path)
    return path


def _login(client, **overrides):
    return client.post("/login", data={**DEMO, **overrides})


def _demo_id(path=None):
    return db.get_user_by_email(DEMO["email"], path)["id"]


def _add_expense(user_id, amount, category, day, description, path=None):
    conn = db.get_db(path)
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, day, description),
        )
        conn.commit()
    finally:
        conn.close()


def _page(client):
    _login(client)
    return client.get("/profile?range=all")


# ------------------------------------------------------------------ db helpers

def test_get_user_by_id_returns_row_without_password_hash(db_path):
    user = db.get_user_by_id(_demo_id(db_path), db_path)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert "password_hash" not in user.keys()
    assert db.get_user_by_id(9999, db_path) is None


def test_expense_summary_totals_for_demo(db_path):
    summary = db.get_expense_summary(_demo_id(db_path), db_path)
    assert summary["total"] == pytest.approx(400.64)
    assert summary["count"] == 8
    assert summary["top_category"] == "Bills"
    assert summary["top_category_total"] == pytest.approx(120.00)


def test_expense_summary_empty_user(db_path):
    new_id = db.create_user("New", "new@example.com", "password123", db_path)
    summary = db.get_expense_summary(new_id, db_path)
    assert summary["total"] == 0
    assert summary["count"] == 0
    assert summary["top_category"] is None


def test_category_totals_ordered_and_sum_to_total(db_path):
    uid = _demo_id(db_path)
    rows = db.get_category_totals(uid, db_path)
    assert [r["category"] for r in rows] == [
        "Bills", "Shopping", "Food", "Transport", "Health", "Entertainment", "Other",
    ]
    assert rows[2]["total"] == pytest.approx(74.90)
    assert sum(r["total"] for r in rows) == pytest.approx(
        db.get_expense_summary(uid, db_path)["total"]
    )


def test_recent_expenses_newest_first_and_limit(db_path):
    uid = _demo_id(db_path)
    rows = db.get_recent_expenses(uid, db_path=db_path)
    assert len(rows) == 8
    assert rows[0]["category"] == "Food" and rows[0]["amount"] == pytest.approx(62.40)
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)

    for i in range(5):
        _add_expense(uid, 1.0, "Other", "2020-01-0%d" % (i + 1), None, db_path)
    assert len(db.get_recent_expenses(uid, db_path=db_path)) == 10
    assert len(db.get_recent_expenses(uid, limit=3, db_path=db_path)) == 3


def test_helpers_scoped_to_user(db_path):
    other = db.create_user("Other", "other@example.com", "password123", db_path)
    _add_expense(other, 999.0, "Travel", "2026-01-01", "Flight", db_path)
    demo = _demo_id(db_path)

    assert db.get_expense_summary(demo, db_path)["count"] == 8
    assert "Travel" not in [r["category"] for r in db.get_category_totals(demo, db_path)]
    assert all(r["category"] != "Travel" for r in db.get_recent_expenses(demo, db_path=db_path))
    assert db.get_expense_summary(other, db_path)["count"] == 1


# ------------------------------------------------------------------ access

def test_profile_redirects_to_login_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_deleted_user_session_redirects(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_redirects_to_profile(client):
    response = _login(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"
    assert client.get("/profile").status_code == 200


def test_login_page_redirects_to_profile_when_logged_in(client):
    _login(client)
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"] == "/profile"


def test_failed_login_does_not_redirect_to_profile(client):
    response = _login(client, password="wrong-password")
    assert response.status_code == 400


# ------------------------------------------------------------------ content

def test_profile_shows_user_details(client):
    response = _page(client)
    assert response.status_code == 200
    assert b"Demo User" in response.data
    assert b"demo@spendly.com" in response.data
    assert b"coming in Step 4" not in response.data


def test_profile_member_since_date(client):
    response = _page(client)
    created = db.get_user_by_email(DEMO["email"])["created_at"]
    parsed = date.fromisoformat(created[:10])
    expected = f"Member since {parsed.day} {parsed:%b %Y}"
    assert expected in response.data.decode()


def test_profile_stats_for_demo(client):
    html = _page(client).data.decode()
    assert "₹400.64" in html
    assert "Top category" in html
    assert "Bills" in html and "₹120.00" in html
    assert re.search(r'stat-label">Expenses</p>\s*<p class="stat-value">8<', html)


def test_profile_category_breakdown_order(client):
    html = _page(client).data.decode()
    section = html.split("Spending by category")[1]
    positions = [section.index(c) for c in
                 ["Bills", "Shopping", "Food", "Transport", "Health", "Entertainment", "Other"]]
    assert positions == sorted(positions)
    assert "₹74.90" in section


def test_profile_recent_expenses_left_of_categories(client):
    html = _page(client).data.decode()
    columns = html.split('class="profile-columns"')[1]
    assert columns.index("Recent expenses") < columns.index("Spending by category")

    css = Path("static/css/profile.css").read_text()
    # Both rows share one 3-column grid and gap so the right column lines up
    # under the third stat tile; recent expenses spans two of the three columns.
    stats = re.search(r"\.profile-stats\s*{([^}]*)}", css).group(1)
    columns = re.search(r"\.profile-columns\s*{([^}]*)}", css).group(1)
    for rule in ("grid-template-columns: repeat(3, 1fr)", "gap: 1.5rem"):
        assert rule in stats and rule in columns
    assert re.search(r"\.profile-columns > :first-child\s*{\s*grid-column:\s*span 2", css)
    assert re.search(
        r"@media \(max-width: 800px\)\s*{\s*\.profile-columns\s*{\s*grid-template-columns:\s*1fr",
        css,
    )


def test_profile_header_is_a_white_card():
    css = Path("static/css/profile.css").read_text()
    header = re.search(r"\.profile-header\s*{([^}]*)}", css).group(1)
    assert "background: var(--paper-card)" in header
    assert "border: 1px solid var(--border)" in header
    assert "border-radius: var(--radius-md)" in header


def test_profile_recent_expenses_and_missing_description(client):
    html = _page(client).data.decode()
    rows = html.split("<tbody>")[1].split("</tbody>")[0]
    assert rows.index("Weekly groceries") < rows.index("Lunch at cafe")
    other_row = [r for r in rows.split("<tr>") if "Other" in r][0]
    assert "—" in other_row
    assert "None" not in rows


def test_profile_empty_state_for_new_user(client):
    client.post("/register", data={"name": "Fresh", "email": "fresh@example.com",
                                   "password": "password123"})
    client.post("/login", data={"email": "fresh@example.com", "password": "password123"})
    response = client.get("/profile")
    html = response.data.decode()
    assert response.status_code == 200
    assert "No expenses yet" in html
    assert "₹0.00" in html
    assert "None" not in html
    assert "<table" not in html


def test_profile_does_not_leak_other_users_expenses(client):
    other = db.create_user("Other", "other@example.com", "password123")
    _add_expense(other, 777.0, "Travel", "2026-01-01", "Secret flight")

    html = _page(client).data.decode()
    assert "Secret flight" not in html and "Travel" not in html

    client.get("/logout")
    client.post("/login", data={"email": "other@example.com", "password": "password123"})
    html = client.get("/profile?range=all").data.decode()
    assert "Secret flight" in html
    assert "Weekly groceries" not in html


# ------------------------------------------------------------------ navbar

def test_navbar_shows_profile_when_logged_in(client):
    out = client.get("/").data
    assert b">Profile</a>" not in out and b">Home</a>" not in out

    _login(client)
    in_ = client.get("/").data
    assert b">Profile</a>" in in_ and b"Sign out" in in_


def test_navbar_swaps_home_and_profile_tabs(client):
    _login(client)

    home = client.get("/").data
    assert b">Profile</a>" in home
    assert b">Home</a>" not in home

    profile = client.get("/profile?range=all").data
    assert b">Home</a>" in profile
    assert b">Profile</a>" not in profile
    assert b"Sign out" in profile


def test_navbar_home_tab_links_to_landing(client):
    _login(client)
    html = client.get("/profile?range=all").data.decode()
    assert re.search(r'<a href="/" class="nav-link-keep">Home</a>', html)


# ------------------------------------------------------------------ security

def test_profile_does_not_render_password_hash(client):
    password_hash = db.get_user_by_email(DEMO["email"])["password_hash"]
    assert password_hash.encode() not in _page(client).data


def test_profile_escapes_html(client):
    uid = db.create_user("<script>alert(1)</script>", "xss@example.com", "password123")
    _add_expense(uid, 5.0, "Other", "2026-01-01", "<script>bad()</script>")
    client.post("/login", data={"email": "xss@example.com", "password": "password123"})
    html = client.get("/profile?range=all").data.decode()
    assert "<script>alert(1)</script>" not in html
    assert "<script>bad()</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html


# ------------------------------------------------------------------ source rules

def test_profile_assets_have_no_hardcoded_urls_or_hex():
    template = Path("templates/profile.html").read_text()
    css = Path("static/css/profile.css").read_text()
    assert 'href="/' not in template and 'src="/' not in template
    assert "<style" not in template and 'style="' not in template
    assert "|safe" not in template
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


# ------------------------------------------------------------------ filters

def test_inr_filter_indian_grouping():
    import app as app_module

    assert app_module.format_inr(123456.5) == "₹1,23,456.50"
    assert app_module.format_inr(1234567) == "₹12,34,567.00"
    assert app_module.format_inr(999) == "₹999.00"
    assert app_module.format_inr(None) == "₹0.00"
