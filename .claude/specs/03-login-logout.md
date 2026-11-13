# Spec: Login and Logout

## Overview
Make the existing `/login` page functional and replace the `/logout` stub. Users submit email and password; the server looks up the user, verifies the password hash, stores the user id in the Flask session, and redirects. Logout clears the session. This is Step 3 of the Spendly roadmap: registration (Step 2) creates accounts, and login establishes the session that Profile (Step 4) and the expense routes (Steps 7–9) will rely on to know who the current user is. Currently `GET /login` only renders a static form that posts to nowhere, and `GET /logout` returns a raw string.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`, `seed_db()`)
- Step 2 — Registration (`create_user`, `get_user_by_email`, users with hashed passwords)

## Routes
- `GET /login` — render the login form; if already logged in, redirect to `/` — public (already exists)
- `POST /login` — validate form, verify credentials, set session, redirect to `/` on success, re-render form with a generic error (HTTP 400/401) on failure — public
- `GET /logout` — clear the session and redirect to `/` — logged-in (a logged-out visitor is simply redirected to `/`; no error)

The login route in `app.py` changes to `@app.route("/login", methods=["GET", "POST"])`. The logout route keeps `GET` (matches the existing route table in CLAUDE.md) and stops returning a raw string.

No other stub route (`/profile`, `/expenses/*`) is touched. Because `/profile` is still a stub until Step 4, a successful login redirects to the landing page, not to `/profile`.

## Database changes
No database changes. `users` already has `email` (UNIQUE NOT NULL) and `password_hash`. The existing `get_user_by_email()` in `database/db.py` already returns a `sqlite3.Row` or `None` and normalises email case, so no new DB helper is required. Password verification (`check_password_hash`) is done against `user["password_hash"]`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — change `action="/login"` to `action="{{ url_for('login') }}"`; re-populate the `email` field on error (`value="{{ email or '' }}"`); never re-populate the password. The `auth-error` block already exists.
  - `templates/base.html` — navbar is session-aware: when `session.user_id` is set, show a "Sign out" link (`url_for('logout')`) instead of "Sign in" / "Get started"; otherwise keep the current links. Use `url_for()` for every link.

## Files to change
- `app.py` — set `app.secret_key`, import `session`/`check_password_hash`, accept POST on `/login`, implement `/logout`
- `templates/login.html` — `url_for`, email re-population
- `templates/base.html` — session-aware navbar

## Files to create
- `tests/test_login_logout.py` — pytest coverage for the Definition of done

## New dependencies
No new dependencies. Flask's built-in signed-cookie `session` and werkzeug's `check_password_hash` are already available.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with `werkzeug.security.check_password_hash`; never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives only in `database/db.py`; the route just reads the form, calls `get_user_by_email`, verifies, sets the session, redirects or renders
- Set `app.secret_key` from an environment variable (e.g. `SECRET_KEY`) with a clearly-labelled development fallback; never leave sessions unsigned
- Normalise email with `strip().lower()` before lookup (same as registration)
- Store only `session["user_id"]` (the integer id) — no password hash, no email, no other user data in the cookie
- Use one generic error, "Invalid email or password.", for both an unknown email and a wrong password, so the form does not reveal which emails are registered
- A blank email or password re-renders the form with an error (do not look up the user)
- On failure render with `render_template` and an error status code — never a raw string; use `abort()` for genuine HTTP errors
- On success call `session.clear()` before setting `session["user_id"]` to avoid session fixation; redirect with `redirect(url_for("landing"))`
- Logout must call `session.clear()` and `redirect(url_for("landing"))`
- Do not implement `/profile`, expense routes, login-required decorators for other pages, "remember me", or password reset — those belong to later steps
- Do not change the port (5001)

## Definition of done
- [ ] `GET /login` returns 200 and shows the form; its form posts via `url_for('login')` with no hardcoded URL in the template
- [ ] Submitting `demo@spendly.com` / `demo123` redirects (302) to `/` and the session contains the demo user's id
- [ ] Email lookup is case-insensitive and whitespace-tolerant (`  DEMO@Spendly.com ` logs in)
- [ ] A user created via `/register` can immediately log in with the same credentials
- [ ] A wrong password re-shows the form with "Invalid email or password." and no session is set
- [ ] An unknown email shows the exact same error message as a wrong password
- [ ] A blank email or blank password shows an error and sets no session
- [ ] On any error the email field keeps its entered value and the password field is empty
- [ ] The session cookie holds only `user_id` (no email, name or hash)
- [ ] While logged in, the navbar shows "Sign out" and hides "Sign in" / "Get started"; while logged out it shows the original links
- [ ] `GET /login` while already logged in redirects to `/`
- [ ] `GET /logout` redirects (302) to `/`, clears the session, and the navbar returns to the logged-out links
- [ ] `GET /logout` while logged out does not error (redirects to `/`)
- [ ] `/profile` and the `/expenses/*` stubs are unchanged
- [ ] `pytest tests/test_login_logout.py` passes, and the existing `pytest` suite still passes
