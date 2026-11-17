# Spec: Add Expense

## Overview
Let a logged-in user record a new expense. A circular **floating action button (FAB)** with a "+" icon is pinned to the bottom-right corner of the home page (`/`) and the profile page (`/profile`) whenever the user is logged in. It links to a new "Add expense" page whose form captures amount, category, date and an optional description. A valid submission inserts the row for the session user and redirects back to the profile page, which shows a one-time "Expense added" confirmation. An invalid submission re-renders the form with an inline error and the user's input preserved. This replaces the `GET /expenses/add` stub. Steps 1–5 built the read side (summary, breakdown, date filter), and this is the first step that writes expense data. It sets the form, validation and "logged-in write" patterns that Edit (Step 8) and Delete (Step 9) will reuse. The FAB is a plain link, so it works without JavaScript.

> Numbering note: `CLAUDE.md` and the stub string in `app.py` refer to this route as "Step 7". This spec is filed as `06` as requested. Implementation updates the `CLAUDE.md` route table and drops the stale stub text.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()`, FK enforcement)
- Step 3: Login and Logout (`session["user_id"]`)
- Step 4: Profile page (`/profile`, `profile.html`, where the user lands after saving and one of the two pages that show the FAB)
- The landing page (`/`, `landing.html`), the other page that shows the FAB to logged-in users
- Step 5: Date filter (the profile's default "Last 7 days" view, see the redirect rule below)

## Routes
- `GET /expenses/add`: render the empty add-expense form. The date defaults to today and the category has no preselection. Logged-in only.
- `POST /expenses/add`: validate the input. If it is valid, insert the expense for `session["user_id"]` and redirect (302) to the profile page. If it is invalid, re-render the form with HTTP 400, an inline error and the submitted values. Logged-in only.

Shared access rules (same as `/profile`):
- No `session["user_id"]`: redirect (302) to `/login`
- Session user id no longer exists in the DB: clear the session and redirect to `/login`
- The `user_id` written to the row comes **only** from the session and never from form data. Any `user_id` field in the POST body is ignored.

Redirect target after a successful save:
- Redirect to `url_for('profile')` with no query string, so the profile page opens on its default **Last 7 days** range (Step 5). An expense dated before that window is saved but not listed until the user widens the filter; this is accepted behaviour.
- Flash the message "Expense added." (category `success`). It shows once on the profile page and disappears on reload.

`/expenses/<id>/edit` and `/expenses/<id>/delete` remain stubs and are not touched.

## Database changes
No schema changes. The existing `expenses` table (`user_id`, `amount REAL`, `category TEXT`, `date TEXT`, `description TEXT NULL`, `created_at`) already holds everything needed.

Add one write helper to `database/db.py`:
- `create_expense(user_id, amount, category, expense_date, description=None, db_path=None)`: insert one row with a parameterised `INSERT`, commit, return `cursor.lastrowid`, and roll back and re-raise on error (same shape as `create_user`). A blank or whitespace-only description is stored as `NULL`.

The helper trusts that its inputs were already validated. Parsing and validating raw form text happens in `app.py`, not in `db.py`.

## Templates
- **Create:**
  - `templates/add_expense.html` extends `base.html` and renders a single card with:
    - an `h1` "Add expense" and a "Back to profile" link (`url_for('profile')`)
    - a `<form method="post" action="{{ url_for('add_expense') }}" novalidate>` with labelled fields:
      - **Amount (₹)**: `<input type="number" name="amount" step="0.01" min="0.01" inputmode="decimal" required>`
      - **Category**: `<select name="category" required>` with a disabled placeholder option ("Choose a category") and one option per allowed category
      - **Date**: `<input type="date" name="date" required>`, defaulting to today and with `max` set to today
      - **Description (optional)**: `<input type="text" name="description" maxlength="200">`
    - an error paragraph (`role="alert"`) above the fields when `error` is set
    - a primary "Save expense" submit button and a secondary "Cancel" link to `url_for('profile')`
    - submitted values (amount, category, date, description) echoed back into the fields on a 400 re-render
- **Modify:**
  - `templates/base.html` renders the FAB once, after `</main>`, only when `session.get("user_id")` is set **and** `request.endpoint` is `landing` or `profile`. Logged-out visitors never see it, and it is not shown on the add-expense page itself or on other pages (login, register, terms, privacy). Because it lives in the shared layout it appears in every state of those pages, including the profile page's "No expenses yet" and "No expenses in this range" empty states:
    - `<a class="fab" href="{{ url_for('add_expense') }}" aria-label="Add expense">`, with a decorative "+" glyph (`aria-hidden="true"`)
    - When the FAB is rendered, `<body>` gets the class `has-fab` so the footer can reserve space for it
  - `templates/profile.html` no longer contains the FAB. On the "No expenses yet" card, change the copy to point at the button, e.g. "Use the + button to record your first expense."
  - `templates/base.html` renders flashed messages (`get_flashed_messages(with_categories=true)`) in a region at the top of `<main>`. Each message is a `<p class="flash flash-{{ category }}" role="status">`.

## Files to change
- `app.py`: replace the `add_expense` stub with a `GET`/`POST` route. Add the `EXPENSE_CATEGORIES` tuple (`Food`, `Transport`, `Bills`, `Health`, `Entertainment`, `Shopping`, `Other`, matching the seed data), `MAX_AMOUNT`, `MAX_DESCRIPTION_LENGTH` and a `_validate_expense(amount, category, expense_date)` helper that returns `(cleaned_values, error)`. Import `flash` and `create_expense`. Reuse the existing strict `_parse_date` for the date field.
- `database/db.py`: add `create_expense`
- `templates/profile.html`: update the empty-state copy
- `templates/base.html`: add the flash message region, and the FAB for logged-in users on the landing and profile pages (plus the `has-fab` body class)
- `static/css/style.css`: add the `.fab` styles and the `.has-fab .footer` spacing (global, because the FAB renders from `base.html`), and the `.flash` / `.flash-success` styles
- `CLAUDE.md`: mark `GET /expenses/add` as implemented (GET + POST, logged-in only) in the route status table

## Files to create
- `templates/add_expense.html`
- `static/css/expense_form.css`: styles for the add-expense card and form, written to be reused by the Edit page in Step 8
- `tests/test_add_expense.py`: pytest coverage for the Definition of done (route behaviour and `create_expense`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders). Never use f-strings or concatenation for values in SQL.
- Passwords hashed with werkzeug. This step never reads or writes `password_hash`.
- Use CSS variables and never hardcode hex values. The FAB uses `--accent` / `--paper-card`, and the flash uses `--accent-light` / `--accent`.
- All templates extend `base.html`
- DB logic lives only in `database/db.py`. The route validates input, calls `create_expense`, then redirects or renders.
- Use `url_for()` for every internal link and form action, and never hardcode `/expenses/add` or `/profile`
- Use `abort()` only for real HTTP errors. Validation failures re-render the form with status 400, like `register`.
- Validation (server-side is the source of truth, and `novalidate` keeps browser bubbles from hiding the server messages):
  - **Amount** is required, parses as a number, is finite, is `> 0` and `<= MAX_AMOUNT` (10,000,000), and has at most 2 decimal places. It is stored rounded to 2 dp. Reject `abc`, `0`, `-5`, `1e309`, `nan`, `inf` and `12.345`.
  - **Category** is required and must be exactly one of `EXPENSE_CATEGORIES`. Any other value is rejected, never stored.
  - **Date** is required and must be a strict `YYYY-MM-DD` real calendar date (reuse `_parse_date`), no later than today
  - **Description** is optional, stripped, and at most `MAX_DESCRIPTION_LENGTH` (200) characters. Blank becomes `NULL`.
  - Report the first failing field with one clear message, e.g. "Enter an amount greater than 0 with up to 2 decimal places."
- Echo submitted values back only through Jinja2 autoescape. Never use `|safe`.
- The FAB is an `<a>` (navigation), not a `<button>`. It needs an accessible name (`aria-label="Add expense"`), a hit target of at least 56×56px, a visible focus ring, `position: fixed` at the bottom-right with a 24px offset (16px under 480px width), and padding that respects `env(safe-area-inset-bottom)`. It must not cover the last table row or footer links, so when the FAB is shown (`body.has-fab`) add bottom padding to `.footer` equal to the FAB height plus its offset, which keeps the footer links clear and leaves the page content above the footer unobstructed.
- Show the FAB only to logged-in users, and only on `landing` and `profile`. Decide this in `base.html` from the session and `request.endpoint`, not in the routes.
- No JavaScript is required for the FAB, the form or the flash message. Do not add a modal.
- Do not add CSRF tokens, Flask-WTF or any new package. Do not add edit/delete controls, categories management, receipts or recurring expenses, because those belong to later steps.
- Do not change the port (5001), other routes, or the `/expenses/<id>/edit` and `/expenses/<id>/delete` stubs
- Invoke the `spendly-ui-ux` skill before building the template/CSS (to reuse existing tokens and patterns) and again afterwards (to check accessibility, contrast and mobile layout)

## Definition of done
- [ ] Logged in, `/profile` shows a circular "+" FAB fixed at the bottom-right that stays visible while scrolling, has the accessible name "Add expense", and appears in all three page states (data, no expenses at all, empty range)
- [ ] Logged in, the home page (`/`) shows the same FAB, and it links to `/expenses/add`
- [ ] Logged out, the home page and every other page show no FAB, and it is also absent from the add-expense, login and register pages when logged in
- [ ] The FAB links to `/expenses/add`, built with `url_for`
- [ ] `GET /expenses/add` while logged in returns 200 with the form. Date is pre-filled with today and capped at today, and Category shows the placeholder.
- [ ] `GET /expenses/add` and `POST /expenses/add` while logged out redirect (302) to `/login`, and nothing is inserted
- [ ] A session whose user no longer exists is cleared and redirected to `/login`
- [ ] Submitting `amount=250.50`, `category=Food`, today's date and a description inserts exactly one row for the session user, redirects to `/profile` (no query string, so it opens on "Last 7 days" with that chip marked current), and shows "Expense added." once (it is gone after a reload)
- [ ] After that save, the profile total and count include the new expense, and the expense appears in the table
- [ ] With the seeded demo user, adding `100.00` to `Food` changes the all-time total from `400.64` to `500.64` and the count from `8` to `9`
- [ ] An expense dated today is listed immediately after saving, in the "Last 7 days" view
- [ ] An expense dated before the last 7 days is saved (it appears under "All time") but is not listed in the default "Last 7 days" view that follows the redirect
- [ ] Leaving the description blank stores `NULL`, and the table shows "—"
- [ ] Each invalid input returns 400, shows an inline `role="alert"` error, preserves the other entered values, and inserts nothing: missing amount, `abc`, `0`, `-5`, `12.345`, `1e309`, `nan`, amount over 10,000,000, missing category, category `Rent` (not in the list), missing date, `2026-13-40`, `2026-1-5`, a future date, and a 201-character description
- [ ] A POST that includes `user_id=<another user's id>` still saves the expense under the session user, and the other user's totals are unchanged
- [ ] A description containing `<script>alert(1)</script>` is stored as text and rendered escaped on the profile page
- [ ] `create_expense` returns the new row id, stores the amount rounded to 2 dp, and uses only bound parameters
- [ ] Every form field has a visible `<label>`, every control is keyboard-reachable with a visible focus ring, and the error is announced
- [ ] At ~375px width: no horizontal scroll, form fields are full width, and the FAB does not overlap the last table row or footer links on either the profile or the home page
- [ ] No hardcoded URLs or hex values in the new and changed templates or CSS, and no inline `<style>` tags
- [ ] The `/expenses/<id>/edit` and `/expenses/<id>/delete` stubs are unchanged
- [ ] `pytest tests/test_add_expense.py` passes, and the full existing `pytest` suite still passes
