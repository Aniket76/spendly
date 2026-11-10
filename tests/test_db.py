import re
import sqlite3
from datetime import date

import pytest
from werkzeug.security import check_password_hash

from database.db import get_db, init_db, seed_db

CATEGORIES = {
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other",
}


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def seeded(db_path):
    init_db(db_path)
    seed_db(db_path)
    return db_path


def _scalar(db_path, sql, params=()):
    conn = get_db(db_path)
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def test_init_db_creates_tables(db_path):
    init_db(db_path)
    conn = get_db(db_path)
    try:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    assert {"users", "expenses"} <= names


def test_init_db_is_idempotent(db_path):
    init_db(db_path)
    init_db(db_path)


def test_seed_creates_demo_user_with_hashed_password(seeded):
    assert _scalar(seeded, "SELECT COUNT(*) FROM users") == 1
    pw_hash = _scalar(
        seeded, "SELECT password_hash FROM users WHERE email = ?", ("demo@spendly.com",)
    )
    assert pw_hash != "demo123"
    assert check_password_hash(pw_hash, "demo123")


def test_seed_creates_eight_expenses_in_all_categories(seeded):
    assert _scalar(seeded, "SELECT COUNT(*) FROM expenses") == 8
    conn = get_db(seeded)
    try:
        cats = {r["category"] for r in conn.execute("SELECT category FROM expenses")}
    finally:
        conn.close()
    assert cats == CATEGORIES


def test_seed_dates_are_iso_and_in_current_month(seeded):
    conn = get_db(seeded)
    try:
        dates = [r["date"] for r in conn.execute("SELECT date FROM expenses")]
    finally:
        conn.close()
    prefix = date.today().strftime("%Y-%m")
    for d in dates:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)
        assert d.startswith(prefix)


def test_seed_is_idempotent(seeded):
    seed_db(seeded)
    assert _scalar(seeded, "SELECT COUNT(*) FROM users") == 1
    assert _scalar(seeded, "SELECT COUNT(*) FROM expenses") == 8


def test_duplicate_email_rejected(seeded):
    conn = get_db(seeded)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("Other", "demo@spendly.com", "x"),
            )
    finally:
        conn.close()


def test_invalid_user_id_rejected(seeded):
    conn = get_db(seeded)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date) "
                "VALUES (?, ?, ?, ?)",
                (9999, 1.0, "Food", "2026-01-01"),
            )
    finally:
        conn.close()
