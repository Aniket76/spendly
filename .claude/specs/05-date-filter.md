# Spec: Date Filter

## Overview
Add a date-range filter to the profile page so a user can narrow their spending summary to a period of interest. The user picks a "from" and/or "to" date, or a quick range (Last 7 days, This month, Last 30 days, All time), and the stat tiles, the category breakdown and the expenses table all recalculate for that range. The page opens on **Last 7 days** by default. This is Step 5 of the Spendly roadmap: Step 4 built the profile page with all-time figures, and the filter is the first interactive control on it. It is a read-only GET filter driven by query-string parameters, so filtered views are bookmarkable and need no new tables or JavaScript. The filter lives inside the profile header card: user details on the left, the filter on the right.

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`, `seed_db()`)
- Step 3 — Login and Logout (`session["user_id"]`)
- Step 4 — Profile page (`/profile`, the `get_expense_summary`, `get_category_totals` and `get_recent_expenses` helpers, `profile.html`, `profile.css`)

## Routes
No new routes. `GET /profile` is extended (logged-in only, unchanged access rules) to accept optional query parameters:

- `date_from` — `YYYY-MM-DD`, inclusive lower bound on `expenses.date`
- `date_to` — `YYYY-MM-DD`, inclusive upper bound on `expenses.date`
- `range=all` — explicit "All time" marker (no date bounds); used by the "All time" chip

Behaviour:
- **No filter parameters at all** (none of `date_from`, `date_to`, `range` present): the page applies the default quick range, **Last 7 days** (today minus 6 days to today), and shows it as selected with the From/To inputs pre-filled
- Any of the three parameters present means the URL is explicit: the dates (if any) are parsed and applied; with no dates (`?range=all`, or the form submitted with both fields empty, `?date_from=&date_to=`) the page shows **all-time** data with no error
- Either date may be given alone (open-ended range) or both together
- Blank values are treated as "not set"
- A value that is not a strictly formatted `YYYY-MM-DD` real calendar date (`2026-13-40`, `abc`, `2026-1-5`, `20261105`) or a range where `date_from` is after `date_to` is invalid: the page still returns 200, shows an inline error message in the filter, and renders the **unfiltered** (all-time) data — never a 500 and never a silently wrong range
- The user id still comes only from `session["user_id"]`; the filter only narrows that user's own rows
- Anonymous visitors are still redirected to `/login` (the query string is not preserved)

`/expenses/add`, `/expenses/<id>/edit` and `/expenses/<id>/delete` remain stubs and are not touched.

## Database changes
No database changes (no new tables, columns or indexes). `expenses.date` is stored as `YYYY-MM-DD` text, so inclusive range checks with `date >= ?` / `date <= ?` compare correctly as strings.

The three existing read helpers in `database/db.py` each gain optional, **keyword-only** arguments `date_from=None` and `date_to=None`, placed **after** `db_path`:
- `get_expense_summary(user_id, db_path=None, *, date_from=None, date_to=None)`
- `get_category_totals(user_id, db_path=None, *, date_from=None, date_to=None)`
- `get_recent_expenses(user_id, limit=10, db_path=None, *, date_from=None, date_to=None)`

Why keyword-only and last: existing callers (notably several calls in `tests/test_profile.py`) pass `db_path` as the second positional argument. Inserting the new arguments before `db_path` would silently bind the test database path to `date_from`.

Rules for these helpers:
- With both new arguments `None`, results are identical to before, so existing callers keep working
- The `WHERE` clause is assembled from fixed string fragments only (`user_id = ?`, `AND date >= ?`, `AND date <= ?`) and the bounds are passed as `?` parameters — user input is never concatenated or f-string-interpolated into SQL
- Every query still filters on `user_id = ?`
- One small private helper in `db.py`, `_date_range_clause(date_from, date_to)`, returns the SQL fragment and its params and is reused by all three functions
- `get_expense_summary` applies the range to total, count **and** top category
- `get_recent_expenses(limit=None)` omits the `LIMIT` clause and returns every matching row; the default `limit=10` is unchanged for other callers
- Parsing and validating the raw query-string text is not DB logic and stays out of `db.py`; the helpers receive either `None` or an ISO date string

## Templates
- **Create:** none
- **Modify:**
  - `templates/profile.html` — the filter lives **inside** the existing `.profile-header` card (no separate filter section). The header has two columns:
    - **Left** (`.profile-user`): the existing user details (eyebrow, name, email, member since)
    - **Right** (`.profile-filter`, `role="group"` labelled by a visually hidden "Filter by date" heading), stacked top to bottom:
      1. a `<form method="get">` whose `action` is `url_for('profile')` with a "From" `<input type="date" name="date_from">`, a "To" `<input type="date" name="date_to">` (each with a visible `<label>`, pre-filled with the applied values) and an "Apply" submit button
      2. quick-range chips in a group labelled "Quick date ranges": "Last 7 days", "This month", "Last 30 days", "All time" (built with `url_for('profile', date_from=..., date_to=...)`; "All time" uses `url_for('profile', range='all')`). The chip matching the applied range gets `aria-current="true"`; "All time" is current when no dates are applied and there is no error
      3. an inline error paragraph (`role="alert"`) when the submitted range was invalid
    - There is **no** "Clear" button, no "Quick ranges:" text label and no "Showing …" range line; the "All time" chip is the way back to the full view
  - The expenses table lists **every** expense in the applied range (no 10-row cap)
  - Empty states are split: if the user has **no expenses at all** keep the existing "No expenses yet" card; if a filter is applied and **matches nothing** show a "No expenses in this range" card with a "clear the filter" link to `url_for('profile', range='all')`, while the filter stays visible in the header
  - The "no expenses at all" check must not be derived from the filtered summary (the route uses an unfiltered count) so a narrow range does not claim the account is empty

## Files to change
- `app.py` — add a strict date parser and range validator (`_parse_date`, `_parse_date_range` returning `(date_from, date_to, error)`), a `_preset_ranges(today=None)` helper (returns `last_7`, `this_month`, `last_30`), the `DEFAULT_PRESET` constant and `INVALID_RANGE_ERROR`; extend the `profile` route to apply the default range when no filter parameters are present, pass the dates to the three DB helpers (with `limit=None` for the expenses list), and pass `date_from`, `date_to`, `filter_error`, `filter_active`, `presets` and `has_expenses` to the template. Import `timedelta`
- `database/db.py` — extend the three read helpers as described above, support `limit=None`, and add the private range-clause helper
- `templates/profile.html` — filter merged into the header card, chips, error, split empty states
- `static/css/profile.css` — `.profile-header` becomes a wrapping two-column flex row (`.profile-user` left, `.profile-filter` right); styles for the filter form, compact chips (32px high, 0.8rem text), the active chip, the error and mobile stacking, using existing CSS variables only
- `tests/test_profile.py` — its helper and four direct page requests that assert all-time figures now request `/profile?range=all`, because a bare `/profile` defaults to Last 7 days; no assertions change
- `CLAUDE.md` — note the date filter on the `GET /profile` row of the route status table

## Files to create
- `tests/test_date_filter.py` — pytest coverage for the Definition of done (route behaviour and the DB helpers)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL; dynamic parts of the `WHERE` clause may only be fixed literal fragments chosen by code, with all values bound via `?`
- Passwords hashed with werkzeug — unchanged; the filter never touches `password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives only in `database/db.py`; the route parses/validates the inputs, calls helpers, renders the template
- Use `url_for()` for every internal link, including the chips — never hardcode `/profile?...`
- The filter uses `method="get"` so URLs are shareable; no JavaScript is required for it to work
- Validate dates with `date.fromisoformat` and require the normalised ISO form to equal the input text; reject anything else instead of passing it to SQL
- Echo applied values back into the inputs only from the validated/normalised dates, and rely on Jinja2 autoescape for anything else — never use `|safe`
- Preset boundaries are computed from `date.today()` in a route helper that accepts an optional `today` argument (for tests), not from JavaScript: Last 7 days = today minus 6 days to today; This month = first of the current month to today; Last 30 days = today minus 29 days to today
- Do not add pagination, sorting, category filtering, text search or charts — those belong to later steps. The expenses table shows all rows in the range
- Do not change the port (5001), the other routes, or the `/expenses/*` stubs
- Invoke the `spendly-ui-ux` skill before building the template/CSS (reuse existing tokens and patterns) and again afterwards to check accessibility and mobile layout

## Definition of done
- [ ] `/profile` with no query string opens on **Last 7 days**: the From/To inputs hold that range, the "Last 7 days" chip has `aria-current="true"`, and the figures cover only those dates
- [ ] `/profile?range=all` shows all-time figures (`400.64` total and `8` expenses for the seeded demo user), and the "All time" chip is the one marked current
- [ ] The filter sits inside the profile header card: user details on the left, the filter on the right with the date pickers (and Apply) on top and the quick-range chips below; there is no separate filter card
- [ ] The chips read "Last 7 days", "This month", "Last 30 days" and "All time", with no "Quick ranges:" label, no "Showing …" line and no "Clear" button
- [ ] Submitting only "From" shows expenses on or after that date; submitting only "To" shows expenses on or before it; submitting both shows the inclusive range
- [ ] An expense dated exactly on the From date and one exactly on the To date are both included
- [ ] The total, expense count, top category, category breakdown and expenses table all reflect the same filtered set, and the category amounts sum to the filtered total
- [ ] With the seeded demo data, filtering to the 1st–10th of the current month gives a total of `208.25` and a count of `4`
- [ ] The expenses table shows **every** expense in the range: a user with 20 expenses sees 20 rows under All time
- [ ] The inputs are pre-filled with the applied dates after submission
- [ ] The URL after applying (`/profile?date_from=...&date_to=...`) can be reloaded or bookmarked and shows the same filtered view
- [ ] A valid range that matches no expenses shows the "No expenses in this range" card with `0.00` totals, no "None" text, the filter still visible and a "clear the filter" link to `/profile?range=all` — and does **not** show the "No expenses yet" message
- [ ] A user with no expenses at all still sees the original "No expenses yet" empty state, with or without a filter
- [ ] `?date_from=abc`, `?date_to=2026-13-40`, `?date_from=2026-1-5`, `?date_from=20261105` and `?date_from=2026-11-20&date_to=2026-11-01` each return 200, show an inline error (`role="alert"`) and the unfiltered all-time data — no 500
- [ ] `?date_from=&date_to=` (empty form fields) is treated as all-time with no error
- [ ] The "All time" chip links to `/profile?range=all`
- [ ] "Last 7 days", "This month" and "Last 30 days" apply the correct inclusive ranges relative to today, and the matching chip is marked `aria-current="true"` (two chips may be current when their ranges coincide, e.g. on the 7th of a month)
- [ ] A user never sees another user's expenses through the filter (verified with two users who have expenses in the same date range)
- [ ] A SQL-injection style value such as `?date_from=2026-01-01' OR '1'='1` is rejected as an invalid date by the route and never reaches the query; passed directly to a helper it is only ever a bound value and cannot widen the result beyond the user's own rows
- [ ] Logged-out access to `/profile?date_from=2026-01-01` still redirects (302) to `/login`
- [ ] `get_expense_summary`, `get_category_totals` and `get_recent_expenses` called without the new arguments return the same results as before (including the default 10-row limit on `get_recent_expenses`)
- [ ] No hardcoded URLs or hex values in the template or `profile.css`; filter styles live in `static/css/profile.css`, not inline
- [ ] The filter is usable at mobile width (~375px) with no horizontal scroll: it drops below the user details, the inputs and Apply stack full width, every control is keyboard-focusable with a visible focus ring, and the error message is announced (`role="alert"`)
- [ ] `/expenses/*` stubs are unchanged
- [ ] `pytest tests/test_date_filter.py` passes, and the existing `pytest` suite still passes
