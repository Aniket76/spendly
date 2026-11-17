import importlib
import re
from datetime import date
from pathlib import Path

import pytest

from database import db

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
ROOT = Path(__file__).resolve().parent.parent


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


def _login(client, **overrides):
    return client.post("/login", data={**DEMO, **overrides})


def _demo_id(path=None):
    conn = db.get_db(path)
    try:
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", (DEMO["email"],)
        ).fetchone()["id"]
    finally:
        conn.close()


def _add_expense(user_id, amount, category, iso_date, description=None, path=None):
    conn = db.get_db(path)
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, iso_date, description),
        )
        conn.commit()
    finally:
        conn.close()


def _month_day(day):
    today = date.today()
    return date(today.year, today.month, day).isoformat()


def _get(client, query=""):
    _login(client)
    return client.get("/profile" + query)


def _html(client, query=""):
    return _get(client, query).get_data(as_text=True)


# ------------------------------------------------------------------ #
# DB helpers                                                          #
# ------------------------------------------------------------------ #


def test_helpers_unchanged_without_range(db_path):
    uid = _demo_id(db_path)
    summary = db.get_expense_summary(uid, db_path)
    assert summary["count"] == 8
    assert round(summary["total"], 2) == 400.64
    totals = db.get_category_totals(uid, db_path)
    assert round(sum(r["total"] for r in totals), 2) == 400.64
    assert len(db.get_recent_expenses(uid, db_path=db_path)) == 8


def test_summary_filters_range(db_path):
    uid = _demo_id(db_path)
    summary = db.get_expense_summary(
        uid, db_path, date_from=_month_day(1), date_to=_month_day(10)
    )
    assert summary["count"] == 4
    assert round(summary["total"], 2) == 208.25
    assert summary["top_category"] == "Bills"
    assert summary["top_category_total"] == 120.00


def test_range_bounds_are_inclusive(db_path):
    uid = _demo_id(db_path)
    rows = db.get_recent_expenses(
        uid, db_path=db_path, date_from=_month_day(3), date_to=_month_day(6)
    )
    assert [r["date"] for r in rows] == [_month_day(6), _month_day(3)]


def test_open_ended_ranges(db_path):
    uid = _demo_id(db_path)
    only_from = db.get_expense_summary(uid, db_path, date_from=_month_day(22))
    assert only_from["count"] == 2
    only_to = db.get_expense_summary(uid, db_path, date_to=_month_day(3))
    assert only_to["count"] == 2


def test_category_totals_and_recent_follow_range(db_path):
    uid = _demo_id(db_path)
    kwargs = {"date_from": _month_day(1), "date_to": _month_day(14)}
    summary = db.get_expense_summary(uid, db_path, **kwargs)
    totals = db.get_category_totals(uid, db_path, **kwargs)
    recent = db.get_recent_expenses(uid, db_path=db_path, **kwargs)
    assert len(recent) == summary["count"] == 5
    assert round(sum(r["total"] for r in totals), 2) == round(summary["total"], 2)
    dates = [r["date"] for r in recent]
    assert dates == sorted(dates, reverse=True)
    limited = db.get_recent_expenses(uid, limit=2, db_path=db_path, **kwargs)
    assert len(limited) == 2


def test_empty_range_summary(db_path):
    uid = _demo_id(db_path)
    summary = db.get_expense_summary(
        uid, db_path, date_from="1999-01-01", date_to="1999-12-31"
    )
    assert summary == {
        "total": 0,
        "count": 0,
        "top_category": None,
        "top_category_total": 0,
    }


def test_range_scoped_to_user(db_path):
    demo = _demo_id(db_path)
    other = db.create_user("Other", "other@example.com", "password123", db_path)
    _add_expense(other, 999.0, "Travel", _month_day(2), path=db_path)
    kwargs = {"date_from": _month_day(1), "date_to": _month_day(10)}
    assert db.get_expense_summary(demo, db_path, **kwargs)["count"] == 4
    other_summary = db.get_expense_summary(other, db_path, **kwargs)
    assert other_summary["count"] == 1
    assert other_summary["total"] == 999.0


def test_injection_text_is_inert(db_path):
    demo = _demo_id(db_path)
    other = db.create_user("Other", "other@example.com", "password123", db_path)
    _add_expense(other, 500.0, "Travel", _month_day(2), path=db_path)
    payload = "2026-01-01' OR '1'='1"
    # The payload is only ever a bound string, so it cannot widen the query
    # beyond the user's own rows and cannot break the statement.
    summary = db.get_expense_summary(demo, db_path, date_from=payload)
    assert summary["count"] == 8
    assert db.get_expense_summary(demo, db_path, date_to=payload)["count"] == 0
    rows = db.get_recent_expenses(demo, db_path=db_path, date_from=payload)
    assert all(r["category"] != "Travel" for r in rows)
    assert db.get_expense_summary(other, db_path, date_to=payload)["count"] == 0


# ------------------------------------------------------------------ #
# Route                                                               #
# ------------------------------------------------------------------ #


def test_all_time_matches_step_4(client):
    html = _html(client, "?range=all")
    assert "₹400.64" in html
    assert re.search(r'stat-label">Expenses</p>\s*<p class="stat-value">8<', html)


def test_default_view_is_last_7_days(client, app_module):
    start, end = app_module._preset_ranges()["last_7"]
    html = _html(client)
    assert f'name="date_from" value="{start}"' in html
    assert f'name="date_to" value="{end}"' in html
    current = re.findall(
        r'<a class="filter-preset"[^>]*aria-current="true"[^>]*>([^<]+)<', html
    )
    assert current == ["Last 7 days"]
    assert html == _html(client, f"?date_from={start}&date_to={end}")


def test_filter_form_present(client):
    html = _html(client)
    assert re.search(r'<label for="date_from">From</label>', html)
    assert re.search(r'<label for="date_to">To</label>', html)
    assert 'type="date" id="date_from" name="date_from"' in html
    assert "Apply" in html
    for text in ("Last 7 days", "This month", "Last 30 days", "All time"):
        assert text in html


def test_from_only_to_only_and_both(client):
    _login(client)
    from_only = client.get(f"/profile?date_from={_month_day(22)}").get_data(
        as_text=True
    )
    assert "Weekly groceries" in from_only
    assert "Lunch at cafe" not in from_only
    to_only = client.get(f"/profile?date_to={_month_day(3)}").get_data(as_text=True)
    assert "Lunch at cafe" in to_only
    assert "Weekly groceries" not in to_only
    both = client.get(
        f"/profile?date_from={_month_day(1)}&date_to={_month_day(10)}"
    ).get_data(as_text=True)
    assert "₹208.25" in both
    assert re.search(r'stat-label">Expenses</p>\s*<p class="stat-value">4<', both)


def test_inputs_prefilled(client):
    start, end = _month_day(1), _month_day(10)
    html = _html(client, f"?date_from={start}&date_to={end}")
    assert f'name="date_from" value="{start}"' in html
    assert f'name="date_to" value="{end}"' in html
    assert ">Clear<" not in html
    assert "Showing" not in html and "Quick ranges" not in html


def test_valid_range_no_matches(client):
    html = _html(client, "?date_from=1999-01-01&date_to=1999-12-31")
    assert "No expenses in this range" in html
    assert "No expenses yet" not in html
    assert "₹0.00" in html
    assert "None" not in html
    assert 'name="date_from"' in html
    assert "clear the filter" in html


def test_new_user_still_sees_no_expenses_yet(app_module):
    db.create_user("Fresh", "fresh@example.com", "password123")
    client = app_module.app.test_client()
    client.post(
        "/login", data={"email": "fresh@example.com", "password": "password123"}
    )
    for query in ("", "?date_from=2026-01-01"):
        html = client.get("/profile" + query).get_data(as_text=True)
        assert "No expenses yet" in html
        assert "No expenses in this range" not in html
        assert "None" not in html


@pytest.mark.parametrize(
    "query",
    [
        "?date_from=abc",
        "?date_to=2026-13-40",
        "?date_from=2026-1-5",
        "?date_from=20261105",
        "?date_from=2026-11-20&date_to=2026-11-01",
    ],
)
def test_invalid_ranges_fall_back(client, query):
    response = _get(client, query)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'role="alert"' in html
    assert "₹400.64" in html
    assert "Clear" not in html.split('class="profile-stats"')[0]


def test_blank_params_are_no_filter(client):
    html = _html(client, "?date_from=&date_to=")
    assert 'role="alert"' not in html
    assert 'class="filter-link"' not in html
    assert "₹400.64" in html


def test_all_time_link_and_no_clear_button(client):
    filtered = _html(client, f"?date_from={_month_day(1)}")
    assert ">Clear<" not in filtered
    assert re.search(
        r'class="filter-preset" href="/profile\?range=all"[^>]*>All time<', filtered
    )


def test_preset_ranges_helper(app_module):
    ranges = app_module._preset_ranges(date(2026, 11, 17))
    assert ranges["last_7"] == ("2026-11-11", "2026-11-17")
    assert ranges["this_month"] == ("2026-11-01", "2026-11-17")
    assert ranges["last_30"] == ("2026-10-19", "2026-11-17")
    edge = app_module._preset_ranges(date(2026, 3, 1))
    assert edge["this_month"] == ("2026-03-01", "2026-03-01")
    assert edge["last_30"] == ("2026-01-31", "2026-03-01")


def test_presets_apply_and_mark_aria_current(client, app_module):
    presets = app_module._preset_ranges()
    for key, label in (
        ("last_7", "Last 7 days"),
        ("this_month", "This month"),
        ("last_30", "Last 30 days"),
    ):
        start, end = presets[key]
        html = _html(client, f"?date_from={start}&date_to={end}")
        current = re.findall(
            r'<a class="filter-preset"[^>]*aria-current="true"[^>]*>([^<]+)<', html
        )
        # Presets can coincide (e.g. on the 7th, This month == Last 7 days).
        assert label in current and "All time" not in current
    assert re.findall(
        r'<a class="filter-preset"[^>]*aria-current="true"[^>]*>([^<]+)<',
        _html(client, "?range=all"),
    ) == ["All time"]


def test_filter_scoped_to_user(app_module):
    other = db.create_user("Other", "other@example.com", "password123")
    _add_expense(other, 777.0, "Travel", _month_day(2), "Secret trip")
    client = app_module.app.test_client()
    client.post("/login", data=DEMO)
    demo_html = client.get(
        f"/profile?date_from={_month_day(1)}&date_to={_month_day(10)}"
    ).get_data(as_text=True)
    assert "Secret trip" not in demo_html
    client.get("/logout")
    client.post(
        "/login", data={"email": "other@example.com", "password": "password123"}
    )
    other_html = client.get(
        f"/profile?date_from={_month_day(1)}&date_to={_month_day(10)}"
    ).get_data(as_text=True)
    assert "Secret trip" in other_html
    assert "Lunch at cafe" not in other_html


def test_injection_value_rejected_by_route(client):
    response = _get(client, "?date_from=2026-01-01'%20OR%20'1'='1")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'role="alert"' in html
    assert "₹400.64" in html


def test_logged_out_redirects_with_query(client):
    response = client.get("/profile?date_from=2026-01-01")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_template_and_css_rules():
    template = (ROOT / "templates" / "profile.html").read_text()
    css = (ROOT / "static" / "css" / "profile.css").read_text()
    for banned in ('href="/', 'src="/', "<style", 'style="', "|safe"):
        assert banned not in template
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


def test_stubs_unchanged(client):
    # /expenses/add and edit are implemented; delete is still a stub.
    response = client.get("/expenses/1/edit")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    delete = client.get("/expenses/1/delete")
    assert delete.status_code == 302
    assert delete.headers["Location"].endswith("/login")


def test_all_expenses_listed_beyond_ten(app_module):
    uid = _demo_id()
    for i in range(12):
        _add_expense(uid, 1.0, "Other", "2020-01-01", f"Old entry {i}")
    assert len(db.get_recent_expenses(uid, limit=None)) == 20
    assert len(db.get_recent_expenses(uid)) == 10
    client = app_module.app.test_client()
    client.post("/login", data=DEMO)
    html = client.get("/profile?range=all").get_data(as_text=True)
    assert html.count("Old entry") == 12
    assert html.count('data-label="Date"') == 20
