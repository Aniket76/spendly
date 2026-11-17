# Spec: Profile Page

## Overview
Replace the `/profile` stub with a real, logged-in page that shows the current user's account details and a summary of their spending. The page shows the user's name, email and join date, headline stats (total spent, number of expenses, top category), a per-category breakdown, and a list of recent expenses. This is Step 4 of the Spendly roadmap: login (Step 3) now stores `session["user_id"]`, and Profile is the first page that consumes it, establishing the "logged-in only" pattern that the expense routes (Steps 7–9) will reuse. Currently `GET /profile` returns the raw string "Profile page — coming in Step 4", and the navbar has no link to it.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables, `get_db()`, `seed_db()`)
- Step 2 — Registration (users exist, `create_user`)
- Step 3 — Login and Logout (`session["user_id"]`, session-aware navbar)

## Routes
- `GET /profile` — render the profile page for the user in the session; if not logged in, redirect to `/login`; if the session's user id no longer exists in the database, clear the session and redirect to `/login` — logged-in

Two existing login redirects change so that `/profile` becomes the landing spot after signing in (this supersedes the Step 3 spec, which redirected to `/` only because `/profile` was still a stub):
- `POST /login` — on success, redirect to `/profile` (via `url_for("profile")`) instead of `/`; failures still re-render the form with HTTP 400 — public
- `GET /login` — if already logged in, redirect to `/profile` instead of `/` — public

`GET /logout` is unchanged and still redirects to `/`.

No other route is added or changed. `/expenses/add`, `/expenses/<id>/edit` and `/expenses/<id>/delete` remain stubs, and no "Add expense" / "Edit" / "Delete" controls are rendered on the profile page.

## Database changes
No database changes. `users` (`id`, `name`, `email`, `created_at`) and `expenses` (`user_id`, `amount`, `category`, `date`, `description`) already hold everything needed. `users.created_at` is stored as `datetime('now')` text (`YYYY-MM-DD HH:MM:SS`).

New read-only helpers are added to `database/db.py` (no inline SQL in `app.py`), all taking an optional `db_path=None` like the existing helpers:
- `get_user_by_id(user_id, db_path=None)` — return the user row or `None`
- `get_expense_summary(user_id, db_path=None)` — return total amount, expense count, and the highest-spend category (or `None` when there are no expenses)
- `get_category_totals(user_id, db_path=None)` — return `(category, total)` rows ordered by total descending
- `get_recent_expenses(user_id, limit=10, db_path=None)` — return the user's newest expenses ordered by `date DESC, id DESC`

Every query filters on `user_id = ?` so a user can only ever see their own data.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; sections for account details (shown in a white card with the same border, radius and padding as the other cards) and stat tiles, followed by a two-column row with "Recent expenses" on the left (2/3 width) and "Spending by category" on the right (1/3 width); the two columns stack (recent expenses first) below 800px; empty state when the user has no expenses
- **Modify:**
  - `templates/base.html` — when `session.get("user_id")` is set, show a context-aware tab next to "Sign out": on the profile page (`request.endpoint == 'profile'`) a "Home" link (`url_for('landing')`), on every other page a "Profile" link (`url_for('profile')`). Never both at once. Both carry the `nav-link-keep` class so they stay visible on mobile

## Files to change
- `app.py` — replace the `/profile` stub; import the new helpers; register `inr` and `human_date` template filters; redirect to `/profile` after login and when an already-logged-in user opens `/login`
- `database/db.py` — add the four read-only helpers above
- `templates/base.html` — context-aware "Home" / "Profile" navbar tab for logged-in users
- `static/css/style.css` — keep the "Home" / "Profile" nav tab visible below 600px; focus ring for nav links; global `.sr-only` utility
- `tests/test_login_logout.py` — update the login redirect assertions to `/profile`; `test_stub_routes_unchanged` no longer checks the `/profile` stub text
- `CLAUDE.md` — update the route status table: `GET /logout` → Implemented, `GET /profile` → Implemented

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — profile-page-only styles, loaded via `{% block head %}` in `profile.html` (no inline `<style>`)
- `tests/test_profile.py` — pytest coverage for the Definition of done

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug — the profile page never reads, shows or passes `password_hash` to the template
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives only in `database/db.py`; the route fetches data, renders the template, done
- Use `url_for()` for every internal link — never hardcode URLs
- Read the user id only from `session["user_id"]`; the route takes no user id from the URL or query string
- Redirect anonymous visitors with `redirect(url_for("login"))`; do not return a raw string
- Money is shown with two decimals and the same currency convention as the rest of the app; format amounts in the template with a single consistent filter/format, not ad hoc per field
- Escape all user-supplied text (name, email, descriptions) — rely on Jinja2 autoescape; never use `|safe`
- Do not implement add, edit or delete expense, filtering, date-range pickers, charts, or editing of profile details — those belong to later steps
- Do not change the port (5001) and do not touch the other stub routes
- Invoke the `spendly-ui-ux` skill before building the template/CSS (reuse existing tokens and patterns) and again afterwards to check accessibility and mobile layout

## Definition of done
- [ ] Visiting `/profile` while logged out redirects (302) to `/login`
- [ ] After logging in as `demo@spendly.com` / `demo123`, `/profile` returns 200 (no raw string) and shows "Demo User" and `demo@spendly.com`
- [ ] The page shows the member-since date derived from `users.created_at`
- [ ] The account details (name, email, member since) sit in a white card matching the stat tiles and other cards, with the same gap below it as between the other boxes
- [ ] Submitting valid credentials at `/login` redirects (302) to `/profile`, and following it shows the profile page
- [ ] A failed login still re-renders the login form with the error (no redirect)
- [ ] `GET /login` while already logged in redirects (302) to `/profile`
- [ ] `GET /logout` still redirects (302) to `/`
- [ ] Total spent equals the sum of the demo user's seeded expenses (`400.64`), and the expense count is `8`
- [ ] The top category is shown correctly (Bills, `120.00`)
- [ ] On a desktop-width window, "Recent expenses" sits on the left taking about two thirds of the row and "Spending by category" sits on the right taking about one third, side by side
- [ ] The two-column row is aligned with the stat tiles above it: the left edge of "Spending by category" lines up with the left edge of the "Top category" tile, and the right edges of both rows line up, with the same gap between boxes in both rows
- [ ] Below 800px the two sections stack vertically (recent expenses first) with no horizontal scroll
- [ ] The category breakdown lists every category the user has spent in, ordered by total descending, with amounts that sum to the total
- [ ] The recent-expenses list shows the newest expenses first with date, category, description and amount; an expense with no description renders cleanly (e.g. an em dash)
- [ ] A newly registered user with no expenses sees a friendly empty state and `0.00` totals — no errors or "None" text
- [ ] A user never sees another user's expenses (verified with two users with different expenses)
- [ ] A session pointing at a deleted/nonexistent user id is cleared and redirected to `/login` instead of raising a 500
- [ ] While logged in on the home page (`/`), the navbar shows "Profile" and "Sign out" and no "Home" tab
- [ ] While logged in on `/profile`, the navbar shows "Home" and "Sign out" and no "Profile" tab; the "Home" tab links to `/`
- [ ] The "Home" / "Profile" tab is still visible at mobile width (~375px)
- [ ] While logged out, the navbar shows the original "Sign in" / "Get started" links and neither tab
- [ ] The password hash does not appear anywhere in the rendered HTML
- [ ] A name or description containing `<script>` renders as escaped text
- [ ] No hardcoded URLs or hex values in `profile.html` / `profile.css`; styles live in `static/css/profile.css`
- [ ] The layout is usable at mobile width (~375px) with no horizontal scroll, and all interactive elements are keyboard-focusable with visible focus
- [ ] `/expenses/*` stubs are unchanged
- [ ] `pytest tests/test_profile.py` passes, and the existing `pytest` suite still passes
