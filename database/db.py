import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)


def get_db(db_path=None):
    """Open a SQLite connection with dict-like rows and FK enforcement on."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Create all tables if they do not exist. Safe to call repeatedly."""
    conn = get_db(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email, db_path=None):
    """Return the user row for an email (case-insensitive), or None."""
    conn = get_db(db_path)
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id, db_path=None):
    """Return the user row (without password_hash) for an id, or None."""
    conn = get_db(db_path)
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def _date_range_clause(date_from, date_to):
    """Return (sql_fragment, params) limiting expenses.date to an inclusive range.

    Both bounds are optional ISO 'YYYY-MM-DD' strings. The fragment is built
    from fixed literals only; the values are returned as bound parameters.
    """
    clause = ""
    params = []
    if date_from:
        clause += " AND date >= ?"
        params.append(date_from)
    if date_to:
        clause += " AND date <= ?"
        params.append(date_to)
    return clause, params


def get_category_totals(user_id, db_path=None, *, date_from=None, date_to=None):
    """Return (category, total) rows for a user, highest total first.

    date_from / date_to optionally limit the rows to an inclusive date range.
    """
    clause, params = _date_range_clause(date_from, date_to)
    conn = get_db(db_path)
    try:
        return conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause + " GROUP BY category "
            "ORDER BY total DESC, category ASC",
            (user_id, *params),
        ).fetchall()
    finally:
        conn.close()


def get_expense_summary(user_id, db_path=None, *, date_from=None, date_to=None):
    """Return total, count and top category for a user's expenses.

    date_from / date_to optionally limit the rows to an inclusive date range.
    Always returns a dict. With no matching expenses, total is 0, count is 0
    and top_category is None.
    """
    clause, params = _date_range_clause(date_from, date_to)
    conn = get_db(db_path)
    try:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses "
            "WHERE user_id = ?" + clause,
            (user_id, *params),
        ).fetchone()
        top = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause + " GROUP BY category "
            "ORDER BY total DESC, category ASC LIMIT 1",
            (user_id, *params),
        ).fetchone()
        return {
            "total": total,
            "count": count,
            "top_category": top["category"] if top else None,
            "top_category_total": top["total"] if top else 0,
        }
    finally:
        conn.close()


def get_recent_expenses(
    user_id, limit=10, db_path=None, *, date_from=None, date_to=None
):
    """Return a user's newest expenses first (date, then id, descending).

    date_from / date_to optionally limit the rows to an inclusive date range.
    limit=None returns every matching row.
    """
    clause, params = _date_range_clause(date_from, date_to)
    sql = (
        "SELECT id, amount, category, date, description FROM expenses "
        "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    conn = get_db(db_path)
    try:
        return conn.execute(sql, (user_id, *params)).fetchall()
    finally:
        conn.close()


def get_expense_by_id(expense_id, user_id, db_path=None):
    """Return one of a user's expenses, or None if it is missing or not theirs."""
    conn = get_db(db_path)
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password, db_path=None):
    """Insert a user with a hashed password and return the new user id.

    Raises sqlite3.IntegrityError if the email is already registered.
    """
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (
                name.strip(),
                email.strip().lower(),
                generate_password_hash(password, method="pbkdf2:sha256"),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_expense(
    user_id, amount, category, expense_date, description=None, db_path=None
):
    """Insert an expense for a user and return the new expense id.

    Inputs are expected to be validated already (see the route). The amount is
    stored rounded to 2 decimals and a blank description is stored as NULL.
    """
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                round(float(amount), 2),
                category,
                expense_date,
                (description or "").strip() or None,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_expense(
    expense_id,
    user_id,
    amount,
    category,
    expense_date,
    description=None,
    db_path=None,
):
    """Update one of a user's expenses; return True if a row was changed.

    The row is matched on both id and user_id, so another user's expense is
    never touched (returns False). Inputs are expected to be validated already.
    The amount is stored rounded to 2 decimals and a blank description as NULL.
    """
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, "
            "description = ? WHERE id = ? AND user_id = ?",
            (
                round(float(amount), 2),
                category,
                expense_date,
                (description or "").strip() or None,
                expense_id,
                user_id,
            ),
        )
        conn.commit()
        return cursor.rowcount == 1
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_expense_by_id(expense_id, user_id, db_path=None):
    """Delete one of a user's expenses; return True if a row was removed.

    The row is matched on both id and user_id, so another user's expense is
    never touched (returns False). A missing id also returns False.
    """
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def seed_db(db_path=None):
    """Insert a demo user and sample expenses once; no-op if users exist."""
    conn = get_db(db_path)
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (
                "Demo User",
                "demo@spendly.com",
                # Explicit method: werkzeug's default (scrypt) is missing on
                # Python builds without OpenSSL scrypt support.
                generate_password_hash("demo123", method="pbkdf2:sha256"),
            ),
        )
        user_id = cursor.lastrowid

        today = date.today()

        def day(d):
            # Days 1-28 are valid in every month.
            return date(today.year, today.month, d).isoformat()

        expenses = [
            (user_id, 12.50, "Food", day(1), "Lunch at cafe"),
            (user_id, 45.00, "Transport", day(3), "Monthly bus pass top-up"),
            (user_id, 120.00, "Bills", day(6), "Electricity bill"),
            (user_id, 30.75, "Health", day(10), "Pharmacy"),
            (user_id, 25.00, "Entertainment", day(14), "Movie tickets"),
            (user_id, 89.99, "Shopping", day(18), "New headphones"),
            (user_id, 15.00, "Other", day(22), None),
            (user_id, 62.40, "Food", day(26), "Weekly groceries"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
