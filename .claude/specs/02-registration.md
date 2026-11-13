# Spec: Registration

## Overview
Make the existing `/register` page functional. Users submit name, email and password; the server validates the input, hashes the password, creates a row in `users`, and redirects to the login page. Registration is the first step of auth on the Spendly roadmap and is required before login (Step 3) and profile (Step 4) can work. Currently `GET /register` only renders a static form that posts to nowhere.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`)

## Routes
- `GET /register` — render the registration form — public (already exists)
- `POST /register` — validate form, create user, redirect to `/login` on success, re-render form with error on failure — public

The route in `app.py` changes to `@app.route("/register", methods=["GET", "POST"])`.

## Database changes
No schema changes. `users` already has `name`, `email` (UNIQUE NOT NULL), `password_hash`, `created_at`.

New helpers in `database/db.py`:
- `create_user(name, email, password, db_path=None)` — hashes the password with werkzeug (`method="pbkdf2:sha256"`, consistent with `seed_db`), inserts the user using a parameterised query, returns the new user id. Raises `sqlite3.IntegrityError` on duplicate email.
- `get_user_by_email(email, db_path=None)` — returns a `sqlite3.Row` or `None` (case-insensitive lookup via a normalised lowercase email).

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html` — change `action="/register"` to `action="{{ url_for('register') }}"`; re-populate `name` and `email` fields on error (`value="{{ name or '' }}"`); never re-populate the password. Error block already exists.

## Files to change
- `app.py` — accept POST on `/register`, validation, call db helpers, redirect
- `database/db.py` — add `create_user` and `get_user_by_email`
- `templates/register.html` — `url_for`, field re-population

## Files to create
- `tests/test_registration.py` — pytest coverage for the Definition of done

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives only in `database/db.py`; the route just validates, calls helpers, redirects or renders
- Validation (server side, in this order): all fields present and non-blank after `strip()`; email contains `@` and a `.` after it; password at least 8 characters; email not already registered
- Normalise email with `strip().lower()` before storing and looking up
- Duplicate email: catch `sqlite3.IntegrityError` (or check first) and show a generic "An account with that email already exists" error — render with HTTP 200 (or 400) via `render_template`, not a raw string
- Use `redirect(url_for("login"))` on success; do not log the user in (sessions are Step 3)
- Do not implement login, logout, sessions or any other stub route
- Do not change the port (5001)

## Definition of done
- [ ] `GET /register` returns 200 and shows the form
- [ ] Submitting valid name, email and an 8+ character password redirects (302) to `/login`
- [ ] A new row exists in `users` with the lowercased email and a `password_hash` that is not the plaintext and verifies with `check_password_hash`
- [ ] Submitting an email that already exists (including `DEMO@spendly.com`, differing in case) re-shows the form with an error and creates no new row
- [ ] Submitting a password shorter than 8 characters shows an error and creates no user
- [ ] Submitting with a blank name or email, or an invalid email, shows an error and creates no user
- [ ] On any error, the name and email fields keep their entered values and the password field is empty
- [ ] The form posts via `url_for('register')`, with no hardcoded URL in the template
- [ ] `pytest tests/test_registration.py` passes
