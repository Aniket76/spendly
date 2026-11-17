# Spec: Edit Expense

## Overview
Let a logged-in user correct one of their own expenses. Each row in the profile page's expense table gets an "Edit" link that opens a pre-filled form for that expense, with the same fields, validation and layout as the Add Expense page (Step 06). A valid submission updates the row and redirects back to the profile page with a one-time "Expense updated." confirmation. An invalid submission re-renders the form with an inline error and the user's input preserved. Expenses that don't exist or belong to another user return 404, so the page never reveals whether another user's expense id exists. This replaces the `GET /expenses/<id>/edit` stub. It is the second write feature in the roadmap and reuses the form, validation and "logged-in write" patterns that Add Expense set up. Delete (the next step) will reuse the ownership-scoped lookup added here.

> Numbering note: `CLAUDE.md` and the stub string in `app.py` call this route "Step 8". This spec is filed as `07` to follow the sequence in `.claude/specs/` (Add Expense was filed as `06`). Implementation updates the `CLAUDE.md` route table and removes the stale stub text.

## Depends on
- Step 01: Database setup (`expenses` table, `get_db()`, FK enforcement)
- Step 03: Login and Logout (`session["user_id"]`)
- Step 04: Profile page (`/profile`, `profile.html` and the expense table that gets the Edit links)
- Step 05: Date filter (the profile's default "Last 7 days" view after the redirect)
- Step 06: Add Expense (`EXPENSE_CATEGORIES`, `_validate_expense`, `expense_form.css`, the flash message region in `base.html`, `add_expense.html` as the form pattern)

## Routes
- `GET /expenses/<int:id>/edit`: render the edit form pre-filled with the expense's current amount (shown with 2 decimals, e.g. `12.50`), category, date and description. Logged-in only, and only for the owner.
- `POST /expenses/<int:id>/edit`: validate the input with the existing `_validate_expense`. If it is valid, update the expense and redirect (302) to the profile page. If it is invalid, re-render the form with HTTP 400, an inline error and the submitted values. Logged-in only, and only for the owner.

Shared access rules, checked in this order on both methods:
1. No `session["user_id"]`: redirect (302) to `/login`
2. Session user id no longer exists in the DB: clear the session and redirect to `/login`
3. No expense with that `id` belongs to the session user (missing, or owned by someone else): `abort(404)`. Ownership is checked **before** validation, so an invalid POST to someone else's expense returns 404, not 400.
- The expense id comes **only** from the URL and the owner **only** from the session. Any `id` or `user_id` field in the POST body is ignored.
- A non-integer id (e.g. `/expenses/abc/edit`) returns 404 through the `<int:id>` converter.

Redirect target after a successful save:
- Redirect to `url_for('profile')` with no query string, so the profile opens on its default **Last 7 days** range. An edited expense dated before that window is saved but not listed until the user widens the filter. This matches Add Expense and is accepted behaviour. Do not add a `next` parameter, because a user-supplied redirect target needs open-redirect handling that is out of scope.
- Flash "Expense updated." (category `success`). It shows once on the profile page and is gone after a reload.
- Saving without changing anything is allowed. It still redirects and flashes.

`/expenses/<id>/delete` stays a stub and is not touched.

## Database changes
No schema changes.

Add two helpers to `database/db.py`, both scoped to the owner so that one user can never read or change another user's row:
- `get_expense_by_id(expense_id, user_id, db_path=None)`: `SELECT id, amount, category, date, description FROM expenses WHERE id = ? AND user_id = ?`. Returns the row or `None`.
- `update_expense(expense_id, user_id, amount, category, expense_date, description=None, db_path=None)`: `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ? AND user_id = ?`, then commit. Returns `True` if a row was updated (`cursor.rowcount == 1`), else `False`. Rolls back and re-raises on error (same shape as `create_expense`). Stores the amount rounded to 2 dp, and stores a blank or whitespace-only description as `NULL`. Never changes `user_id` or `created_at`.

The helpers trust that their inputs were already validated. Parsing and validating form text stays in `app.py`.

## Templates
- **Create:**
  - `templates/edit_expense.html` extends `base.html`, loads `css/expense_form.css` in the `head` block, and mirrors `add_expense.html`:
    - title block "Edit expense — Spendly"
    - an `h1` "Edit expense" and a "Back to profile" link (`url_for('profile')`)
    - an error paragraph (`id="form-error"`, `role="alert"`) when `error` is set, linked to the amount field with `aria-describedby`, as on the add page
    - `<form method="post" action="{{ url_for('edit_expense', id=expense_id) }}" novalidate>` with the same four labelled fields, attributes and `max="{{ today }}"` on the date as the add form
    - fields filled from `values` (the stored expense on GET, the submitted values on a 400 re-render)
    - a primary "Save changes" submit button and a secondary "Cancel" link to `url_for('profile')`
    - no delete control (that comes in the next step)
- **Modify:**
  - `templates/profile.html`: add a last column to the expense table:
    - header `<th scope="col"><span class="sr-only">Actions</span></th>`
    - per row, `<td data-label="Actions" class="col-actions"><a class="expense-edit-link" href="{{ url_for('edit_expense', id=e.id) }}" aria-label="Edit {{ e.category }} expense of {{ e.amount | inr }} on {{ e.date | human_date }}">Edit</a></td>`
    - the link works in every filter state, and the table still reads cleanly in its stacked mobile layout

## Files to change
- `app.py`: replace the `edit_expense` stub with a `GET`/`POST` route that follows the access rules above. Reuse `EXPENSE_CATEGORIES`, `_validate_expense` and `flash`. Import `get_expense_by_id`, `update_expense` and `abort`. If `update_expense` returns `False` (the row vanished between the check and the update), `abort(404)`.
- `database/db.py`: add `get_expense_by_id` and `update_expense`
- `templates/profile.html`: add the Actions column and the per-row Edit link
- `static/css/profile.css`: styles for `.col-actions` and `.expense-edit-link` (right-aligned on desktop, a full-row tap target of at least 44×44px in the stacked mobile layout, visible focus ring)
- `CLAUDE.md`: mark `GET/POST /expenses/<id>/edit` as implemented (logged-in, owner only, 404 otherwise) in the route status table

## Files to create
- `templates/edit_expense.html`
- `tests/test_edit_expense.py`: pytest coverage for the Definition of done (route behaviour, ownership rules and both DB helpers)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders). Never use f-strings or concatenation for values in SQL.
- Passwords hashed with werkzeug. This step never reads or writes `password_hash`.
- Use CSS variables and never hardcode hex values. Reuse the existing tokens and the `.filter-link` / focus-ring patterns from `profile.css`.
- All templates extend `base.html`
- DB logic lives only in `database/db.py`. The route checks access, validates, calls the helper, then redirects or renders.
- Every ownership check happens in SQL (`WHERE id = ? AND user_id = ?`), never by fetching a row and comparing `user_id` in Python only. The `UPDATE` itself must also include `AND user_id = ?`.
- Missing and not-yours both return the same 404. Never return 403, which would confirm that the id exists.
- Use `abort(404)` for not-found or not-yours. Validation failures re-render the form with status 400, like Add Expense.
- Reuse `_validate_expense` unchanged, so editing applies exactly the same rules as adding (amount > 0, ≤ 10,000,000, ≤ 2 dp; category in the list; strict date no later than today; description ≤ 200 chars, blank → `NULL`). Do not copy or fork the validation.
- Use `url_for()` for every internal link and form action. Never hardcode `/expenses/...` or `/profile`.
- Echo stored and submitted values only through Jinja2 autoescape. Never use `|safe`.
- Format the stored amount for the form in the route (e.g. `f"{row['amount']:.2f}"`) so `12.5` shows as `12.50`. Do not show it in rupee format, because the `number` input needs a plain number.
- If a stored category is not in `EXPENSE_CATEGORIES`, the select falls back to the "Choose a category" placeholder and the user must pick a valid one before saving.
- No JavaScript is needed. Do not add a modal or inline editing in the table.
- Do not add CSRF tokens, Flask-WTF or any new package (this matches Add Expense). Do not add delete controls, bulk edit or an edit history.
- Do not change the port (5001), other routes, `add_expense.html`, or the `/expenses/<id>/delete` stub
- Invoke the `spendly-ui-ux` skill before building the template/CSS (to reuse existing tokens and patterns) and again afterwards (to check accessibility, contrast and mobile layout)

## Definition of done
- [ ] Logged in, every row in the `/profile` expense table has an "Edit" link built with `url_for` that points to `/expenses/<that id>/edit` and has an accessible name naming the category, amount and date
- [ ] `GET /expenses/<id>/edit` for one of your own expenses returns 200 with the heading "Edit expense" and the fields pre-filled: amount with 2 decimals (seeded `12.5` shows as `12.50`), the stored category selected, the stored date, and the stored description (empty when `NULL`)
- [ ] `GET` and `POST` while logged out redirect (302) to `/login`, and nothing is changed
- [ ] A session whose user no longer exists is cleared and redirected to `/login`
- [ ] `GET` and `POST` for an id that doesn't exist return 404
- [ ] `GET` and `POST` for another user's expense return 404, and that expense is unchanged in the DB (also when the POST body is invalid)
- [ ] `/expenses/abc/edit` returns 404
- [ ] Changing the amount to `99.99`, the category to `Transport`, the date to today and the description to "Taxi home" updates that one row, redirects to `/profile` with no query string, and shows "Expense updated." once (it is gone after a reload)
- [ ] After that save, the expense table and the profile totals show the new values, the expense count is unchanged, and no new row was inserted
- [ ] With the seeded demo user, changing the `12.50` Food expense to `112.50` changes the all-time total from `400.64` to `500.64`, and the count stays at `8`
- [ ] Clearing the description stores `NULL`, and the table shows "—"
- [ ] Submitting the form unchanged still redirects with the flash and leaves the row as it was
- [ ] Each invalid input returns 400, shows an inline `role="alert"` error, keeps the submitted values in the fields, and leaves the stored row unchanged: missing amount, `abc`, `0`, `-5`, `12.345`, `1e309`, `nan`, amount over 10,000,000, missing category, category `Rent`, missing date, `2026-13-40`, `2026-1-5`, a future date, and a 201-character description
- [ ] A POST that includes `user_id=<another user's id>` or `id=<another expense id>` in the body updates only the URL's expense, which stays owned by the session user, and the other user's data is unchanged
- [ ] A description containing `<script>alert(1)</script>` is stored as text and rendered escaped on both the edit form and the profile page
- [ ] `get_expense_by_id` returns the row for the owner and `None` for any other user id. `update_expense` returns `True` and changes only the target row for the owner, and returns `False` and changes nothing for any other user id. Both use only bound parameters.
- [ ] `update_expense` never changes `user_id` or `created_at`
- [ ] Every form field has a visible `<label>`, every control and every Edit link is keyboard-reachable with a visible focus ring, and the error is announced
- [ ] At ~375px width: no horizontal scroll on the edit page or the profile table, form fields are full width, the Edit link is a tap target of at least 44×44px, and the FAB does not cover the last row's Edit link
- [ ] No hardcoded URLs or hex values in the new and changed templates or CSS, and no inline `<style>` tags
- [ ] The `/expenses/<id>/delete` stub and `add_expense.html` are unchanged
- [ ] `pytest tests/test_edit_expense.py` passes, and the full existing `pytest` suite (including `test_add_expense.py` and `test_profile.py`) still passes
