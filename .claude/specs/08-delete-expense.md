# Spec: Delete Expense

## Overview
Let a logged-in user permanently remove one of their own expenses. Each row in the profile page's expense table gets a "Delete" link next to "Edit", and the Edit Expense page gets a "Delete this expense" link. Both open a confirmation page that shows the expense's date, category, description and amount, with a danger "Delete expense" button and a "Cancel" link. Only the confirmation form's POST deletes anything. Opening the page with a GET never changes data, so link prefetching, crawlers or a stray click can't delete an expense. After a delete, the user goes back to the profile page with a one-time "Expense deleted." message. Expenses that don't exist or belong to another user return 404, the same as Edit, so the page never reveals whether another user's expense id exists. This replaces the `GET /expenses/<id>/delete` stub, which is the last stub route, so it completes the add / edit / delete cycle for expenses. It reuses the ownership-scoped `get_expense_by_id` helper and the "logged-in write" access pattern from Edit Expense.

> Numbering note: `CLAUDE.md` and the stub string in `app.py` call this route "Step 9". This spec is filed as `08` to follow the sequence in `.claude/specs/` (Edit Expense was filed as `07`). Implementation updates the `CLAUDE.md` route table and removes the stale stub text.

## Depends on
- Step 01: Database setup (`expenses` table, `get_db()`, FK enforcement)
- Step 03: Login and Logout (`session["user_id"]`)
- Step 04: Profile page (`/profile`, `profile.html` and its expense table)
- Step 05: Date filter (the profile's default "Last 7 days" view after the redirect)
- Step 06: Add Expense (`expense_form.css`, the flash message region in `base.html`)
- Step 07: Edit Expense (`get_expense_by_id`, the Actions column with `.col-actions` / `.expense-edit-link`, `edit_expense.html`)

## Routes
- `GET /expenses/<int:id>/delete`: render the confirmation page for that expense. It never changes data. Logged-in only, and only for the owner.
- `POST /expenses/<int:id>/delete`: delete the expense and redirect (302) to the profile page. Logged-in only, and only for the owner.

The route is registered with `methods=["GET", "POST"]`. Any other method returns 405 (Flask's default).

Shared access rules, checked in this order on both methods (the same as Edit Expense):
1. No `session["user_id"]`: redirect (302) to `/login`
2. Session user id no longer exists in the DB: clear the session and redirect to `/login`
3. No expense with that `id` belongs to the session user (missing, or owned by someone else): `abort(404)`
- The expense id comes **only** from the URL and the owner **only** from the session. Any `id` or `user_id` field in the POST body is ignored.
- A non-integer id (e.g. `/expenses/abc/delete`) returns 404 through the `<int:id>` converter.
- If `delete_expense_by_id` returns `False` (the row vanished between the check and the delete, e.g. a double submit from two tabs), `abort(404)`.

Redirect target after a successful delete:
- Redirect to `url_for('profile')` with no query string, so the profile opens on its default **Last 7 days** range. This matches Add and Edit. Do not add a `next` parameter, because a user-supplied redirect target needs open-redirect handling that is out of scope.
- Flash "Expense deleted." (category `success`). It shows once on the profile page and is gone after a reload.
- If the deleted expense was the user's last one, the profile shows its existing "no expenses yet" empty state.

## Database changes
No schema changes. `expenses` has no child tables, so deleting a row needs no cascade.

Add one helper to `database/db.py`, scoped to the owner so that one user can never delete another user's row:
- `delete_expense_by_id(expense_id, user_id, db_path=None)`: `DELETE FROM expenses WHERE id = ? AND user_id = ?`, then commit. Returns `True` if a row was deleted (`cursor.rowcount == 1`), else `False`. Rolls back and re-raises on error (the same shape as `update_expense`).
- Name it `delete_expense_by_id`, not `delete_expense`, so it doesn't clash with the `delete_expense` route function in `app.py` and so it pairs with `get_expense_by_id`.

Reuse the existing `get_expense_by_id(expense_id, user_id)` for the ownership check and for the details shown on the confirmation page. Don't add another lookup.

## Templates
- **Create:**
  - `templates/delete_expense.html` extends `base.html` and loads `css/expense_form.css` in the `head` block, so it shares the card layout with the add and edit pages:
    - title block "Delete expense — Spendly"
    - a "Back to profile" link (`url_for('profile')`)
    - a card (`aria-labelledby` its heading) with an `h1` "Delete expense?"
    - a summary of the expense as a definition list (`<dl>`) of Date (`| human_date`), Category, Description (`—` when `NULL`) and Amount (`| inr`)
    - a warning line: "This can't be undone."
    - `<form method="post" action="{{ url_for('delete_expense', id=expense.id) }}">` containing only a danger submit button "Delete expense" (no hidden id or user_id fields)
    - a secondary "Cancel" link to `url_for('profile')`
- **Modify:**
  - `templates/profile.html`: in each row's existing `col-actions` cell, add a Delete link after the Edit link: `<a class="expense-delete-link" href="{{ url_for('delete_expense', id=e.id) }}" aria-label="Delete {{ e.category }} expense of {{ e.amount | inr }} on {{ e.date | human_date }}">Delete</a>`. Both links stay usable in the stacked mobile layout.
  - `templates/edit_expense.html`: below the form actions, add a quieter danger-styled link "Delete this expense" to `url_for('delete_expense', id=expense_id)`. It is a link to the confirmation page, never a button that deletes directly.

## Files to change
- `app.py`:
  - Replace the `delete_expense` stub with a `GET`/`POST` route that follows the access rules above. GET renders `delete_expense.html` with `expense`. POST calls `delete_expense_by_id`, flashes and redirects.
  - Import `delete_expense_by_id`
  - Remove the now-empty "Placeholder routes — students will implement these" comment block
- `database/db.py`: add `delete_expense_by_id`
- `templates/profile.html`: add the per-row Delete link
- `templates/edit_expense.html`: add the "Delete this expense" link
- `static/css/profile.css`: style `.expense-delete-link` next to `.expense-edit-link`. Use `--danger` for the text colour and the same focus-ring pattern. Lay the two links out with a gap on desktop, and on the stacked mobile layout make each one a tap target of at least 44×44px. The actions cell must not cause horizontal scroll at 375px.
- `static/css/expense_form.css`: add a danger button (`.btn-danger`, using `--danger` / `--danger-light` with white text on `--danger`) and styles for the confirmation summary (`.expense-summary` `<dl>`), the warning line and the edit page's "Delete this expense" link
- `CLAUDE.md`: change the route table row to `GET/POST /expenses/<id>/delete` as implemented (logged-in, owner only, 404 otherwise; GET shows a confirmation page and POST deletes, then redirects to `/profile`). Reached from the Delete link on each profile row and from the edit page.

## Files to create
- `templates/delete_expense.html`
- `tests/test_delete_expense.py`: pytest coverage for the Definition of done (route behaviour, ownership rules, GET not deleting anything, and the DB helper)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders). Never use f-strings or concatenation for values in SQL.
- Passwords hashed with werkzeug. This step never reads or writes `password_hash`.
- Use CSS variables and never hardcode hex values. Reuse `--danger` / `--danger-light` and the existing focus-ring patterns.
- All templates extend `base.html`
- DB logic lives only in `database/db.py`. The route checks access, calls the helper, then redirects or renders.
- **GET must never delete.** Only `POST` removes a row. Never delete on a GET request, and never use a JS `confirm()` dialog in place of the confirmation page.
- Every ownership check happens in SQL. The `DELETE` itself must include `WHERE id = ? AND user_id = ?`, even though the route already checked ownership with `get_expense_by_id`.
- Missing and not-yours both return the same 404. Never return 403, which would confirm that the id exists.
- Use `abort(404)` for not-found or not-yours. Do not return error strings.
- Use `url_for()` for every internal link and form action. Never hardcode `/expenses/...` or `/profile`.
- Echo stored values only through Jinja2 autoescape. Never use `|safe`.
- Deletes are hard deletes. Do not add a soft-delete column, undo, a trash view, or bulk delete.
- No JavaScript is needed. Do not add a modal.
- Do not add CSRF tokens, Flask-WTF or any new package (this matches Add and Edit Expense). Requiring POST plus a confirmation page is the protection in scope for this step.
- Do not change the port (5001), the add or edit routes' behaviour, or `_validate_expense`
- Invoke the `spendly-ui-ux` skill before building the template/CSS (to reuse existing tokens and patterns) and again afterwards (to check accessibility, contrast of the danger button, and mobile layout)

## Definition of done
- [ ] Logged in, every row in the `/profile` expense table has a "Delete" link next to "Edit", built with `url_for`, that points to `/expenses/<that id>/delete` and has an accessible name naming the category, amount and date
- [ ] The edit page for an expense has a "Delete this expense" link to that expense's confirmation page
- [ ] `GET /expenses/<id>/delete` for one of your own expenses returns 200 with the heading "Delete expense?", shows the expense's date, category, description (or "—") and amount, and has a POST form and a Cancel link back to `/profile`
- [ ] Opening the confirmation page (GET) leaves the expense in the DB, even after several GETs
- [ ] Clicking Cancel returns to `/profile` and the expense is still listed
- [ ] `POST /expenses/<id>/delete` for one of your own expenses removes exactly that row, redirects to `/profile` with no query string, and shows "Expense deleted." once (it is gone after a reload)
- [ ] With the seeded demo user, deleting the `12.50` Food expense changes the all-time total from `400.64` to `388.14` and the count from `8` to `7`, and the other 7 rows are unchanged
- [ ] Deleting a user's only expense shows the profile's existing "no expenses yet" empty state
- [ ] `GET` and `POST` while logged out redirect (302) to `/login`, and nothing is deleted
- [ ] A session whose user no longer exists is cleared and redirected to `/login`
- [ ] `GET` and `POST` for an id that doesn't exist return 404
- [ ] `GET` and `POST` for another user's expense return 404, and that expense is still in the DB
- [ ] A second `POST` for an expense that was already deleted returns 404
- [ ] `/expenses/abc/delete` returns 404, and a `PUT` or `DELETE` request returns 405
- [ ] A POST that includes `user_id=<another user's id>` or `id=<another expense id>` in the body deletes only the URL's expense (owned by the session user), and the other user's data is unchanged
- [ ] A description containing `<script>alert(1)</script>` is rendered escaped on the confirmation page
- [ ] `delete_expense_by_id` returns `True` and removes only the target row for the owner, and returns `False` and removes nothing for any other user id or a missing id. It uses only bound parameters.
- [ ] The Delete links, the danger button and Cancel are keyboard-reachable with a visible focus ring, and the danger button's text meets WCAG AA contrast
- [ ] At ~375px width: no horizontal scroll on the confirmation page or the profile table, Edit and Delete are each a tap target of at least 44×44px, and the FAB does not cover the last row's actions
- [ ] No hardcoded URLs or hex values in the new and changed templates or CSS, and no inline `<style>` tags
- [ ] `app.py` has no remaining stub routes or "coming in Step" strings, and `CLAUDE.md` marks the delete route as implemented
- [ ] `pytest tests/test_delete_expense.py` passes, and the full existing `pytest` suite (including `test_edit_expense.py` and `test_profile.py`) still passes
