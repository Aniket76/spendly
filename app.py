import os
import sqlite3
from datetime import date, timedelta

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_category_totals,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
# Development fallback only — set SECRET_KEY in the environment for real use.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Template filters                                                    #
# ------------------------------------------------------------------ #

@app.template_filter("inr")
def format_inr(value):
    """Format a number as rupees with Indian digit grouping: ₹1,23,456.50."""
    amount = round(float(value or 0), 2)
    sign = "-" if amount < 0 else ""
    whole, fraction = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}₹{whole}.{fraction}"


@app.template_filter("human_date")
def format_human_date(value):
    """Turn 'YYYY-MM-DD[ HH:MM:SS]' text into '17 Nov 2026'."""
    parsed = date.fromisoformat(str(value)[:10])
    return f"{parsed.day} {parsed:%b %Y}"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


DUPLICATE_EMAIL_ERROR = "An account with that email already exists."


def _validate_registration(name, email, password):
    """Return an error message for invalid registration input, else None."""
    if not name or not email or not password:
        return "All fields are required."
    local, _, domain = email.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return None


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = _validate_registration(name, email, password)
    if error is None and get_user_by_email(email) is not None:
        error = DUPLICATE_EMAIL_ERROR
    if error is None:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = DUPLICATE_EMAIL_ERROR
    if error is not None:
        return (
            render_template("register.html", error=error, name=name, email=email),
            400,
        )
    return redirect(url_for("login"))


LOGIN_ERROR = "Invalid email or password."


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email) if email and password else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error=LOGIN_ERROR, email=email), 400

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms-and-conditions")
def terms_and_conditions():
    return render_template("terms_and_conditions.html")


@app.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")


DEFAULT_PRESET = "last_7"
INVALID_RANGE_ERROR = "Enter valid dates, with the start on or before the end."


def _parse_date(text):
    """Return text as a date if it is strictly YYYY-MM-DD, else raise ValueError."""
    parsed = date.fromisoformat(text)
    if parsed.isoformat() != text:
        raise ValueError(text)
    return parsed


def _parse_date_range(raw_from, raw_to):
    """Validate the filter inputs; return (date_from, date_to, error).

    Blank values mean "not set". Any invalid input or a reversed range returns
    (None, None, error) so the caller falls back to all-time data.
    """
    raw_from, raw_to = (raw_from or "").strip(), (raw_to or "").strip()
    try:
        start = _parse_date(raw_from) if raw_from else None
        end = _parse_date(raw_to) if raw_to else None
    except ValueError:
        return None, None, INVALID_RANGE_ERROR
    if start and end and start > end:
        return None, None, INVALID_RANGE_ERROR
    return (
        start.isoformat() if start else None,
        end.isoformat() if end else None,
        None,
    )


def _preset_ranges(today=None):
    """Return the quick-filter ranges as (date_from, date_to) ISO pairs."""
    today = today or date.today()
    return {
        "last_7": ((today - timedelta(days=6)).isoformat(), today.isoformat()),
        "this_month": (today.replace(day=1).isoformat(), today.isoformat()),
        "last_30": ((today - timedelta(days=29)).isoformat(), today.isoformat()),
    }


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    presets = _preset_ranges()
    if any(key in request.args for key in ("date_from", "date_to", "range")):
        date_from, date_to, filter_error = _parse_date_range(
            request.args.get("date_from"), request.args.get("date_to")
        )
    else:
        # No filter in the URL: open on the default quick range.
        (date_from, date_to), filter_error = presets[DEFAULT_PRESET], None
    filter_active = date_from is not None or date_to is not None
    summary = get_expense_summary(user_id, date_from=date_from, date_to=date_to)
    # An unfiltered count tells "no expenses at all" apart from "none in range".
    has_expenses = (
        get_expense_summary(user_id)["count"] > 0 if filter_active else summary["count"] > 0
    )

    return render_template(
        "profile.html",
        user=user,
        summary=summary,
        category_totals=get_category_totals(
            user_id, date_from=date_from, date_to=date_to
        ),
        expenses=get_recent_expenses(
            user_id, limit=None, date_from=date_from, date_to=date_to
        ),
        date_from=date_from,
        date_to=date_to,
        filter_active=filter_active,
        filter_error=filter_error,
        has_expenses=has_expenses,
        presets=presets,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
