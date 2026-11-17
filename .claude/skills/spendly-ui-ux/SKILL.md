---
name: spendly-ui-ux
description: Audit, build and improve the UI/UX of the Spendly Flask expense tracker (templates, style.css, main.js) — accessibility (WCAG AA), design tokens, forms and feedback states, mobile responsiveness, and expense list/dashboard/chart screens. Use this whenever a task creates or edits any page or template, adds a route that renders HTML, or touches static CSS/JS (new page, new form, table, chart, navbar, modal, profile/add/edit expense screens), and whenever the user mentions Spendly UI, UX, design, styling, polish, contrast, focus, mobile or responsive layout, flash messages, validation, empty/error states, or says a page "looks off", even if they don't say "UI/UX".
---

# Spendly UI/UX advancement

Spendly is a small Flask + SQLite + Jinja + vanilla JS app. Its visual identity is already set: warm paper/ink neutrals, a dark green accent, amber secondary, DM Serif Display headings and DM Sans body, all defined as CSS variables at the top of `static/css/style.css`. This skill improves screens **within** that identity. It does not rebrand, and it does not add dependencies.

## Workflow: audit first, then implement

The owner wants to see findings before code changes, because UI edits are cheap to make and annoying to undo across many files.

1. **Explore.** CLAUDE.md requires a builtin Explore subagent before implementing any feature. Use one to read the target page's template, `base.html`, the relevant parts of `style.css`, `main.js`, and the route in `app.py`. Do not skip this; tokens and components get reused across pages and you need to know what already exists.
2. **Audit.** Review the target against `references/audit-checklist.md`. Produce a short findings list, each item with: file and line/selector, what is wrong, why it matters to a user, and the fix. Group by severity (blocks use, hurts use, polish). Keep it to what you actually observed in the code.
3. **Stop and confirm.** Show the findings and ask which to apply. If the user already said "just fix it" or named specific fixes, apply those without waiting.
4. **Implement** the approved items following the rules below.
5. **Verify.** Run `pytest` via a subagent (CLAUDE.md policy). Then re-check the audit items you changed (grep for leftover hardcoded colors, inline styles, missing labels). If the app can be run on port 5001 and a browser tool is available, look at the page at ~375px and ~1024px wide.
6. **Report** what changed and what you left alone, in a few lines.

If the user asks for a spec/plan instead, hand off to the project's `create-spec` / `create-plan` skills rather than duplicating them.

## New page or template mode

When the task is to create a page (including implementing a stub route such as profile, add, or edit expense), run this lighter flow instead of a full audit, because there is no existing page to audit:

1. **Before building:** read `references/patterns.md` for the matching pattern (form, list, dashboard, error page) and `references/design-tokens.md`. Reuse existing classes and tokens; add a token before using a new value. Plan the page's empty, error and mobile (375px) states up front, since retrofitting them later is where most UX debt comes from.
2. **While building:** extend `base.html`, put page-specific CSS in its own file loaded via `{% block head %}`, use `url_for()`, label every input, and wire flash messages for success and failure.
3. **After building:** run the relevant sections of `references/audit-checklist.md` against the new page (contrast, focus, labels, no raw hex, no inline styles, 44px targets, no horizontal scroll at 360px) and fix what fails before reporting done. Keep this check short and report only what you fixed or deliberately left.

This skill covers presentation only. Route logic, database work and the step scope rules in CLAUDE.md still apply and still decide what you are allowed to implement.

## Hard constraints (from CLAUDE.md)

These exist because the project is intentionally lightweight; breaking them creates review friction and defeats the point of the app.

- Flask, SQLite, Jinja, **vanilla JS only**. No npm, no frameworks, no CSS frameworks, no new pip packages.
- Every template extends `base.html`; every internal link uses `url_for()`.
- Page-specific styles go in their own file under `static/css/` (e.g. `dashboard.css`) loaded through `{% block head %}`. No `<style>` blocks. Avoid inline `style=""` attributes too; use a class or a CSS custom property set via a class.
- DB logic stays in `database/db.py`; routes stay thin. Format display values (₹, dates) with Jinja filters registered in `app.py`, not with logic in templates or routes.
- Use `abort()` for HTTP errors. Do not implement stub routes (`/profile`, `/expenses/...`) unless the user's task targets that step. You may design their UI in a spec when asked.
- Charts: CSS-only bars or inline SVG generated in the template. No chart library.

## Design rules

Read `references/design-tokens.md` before touching CSS. The short version:

- **Use tokens, never raw hex.** If a needed color/size/shadow has no token, add one to `:root` first, then use it. Existing offenders (hero green, mock bar colors, `#f5c6c2` border) should be tokenized when you touch the surrounding rules.
- **Accessibility target is WCAG 2.1 AA.** Text contrast 4.5:1 (3:1 for large text and UI borders). `--ink-faint` (#a0a0a0) fails on paper; do not use it for text. Never remove focus outlines without a visible `:focus-visible` replacement (2px ring, offset, accent color).
- **Mobile first-class.** Design for 375px, then widen. Touch targets at least 44×44px. Never hide a primary action at small widths (the navbar currently hides "Sign in" under 600px; fix with a compact nav pattern instead). Lists of records become stacked cards on narrow screens rather than horizontally scrolling tables. Use `inputmode`, `autocomplete`, and correct `type` on inputs so mobile keyboards help.
- **Respect user settings.** Wrap non-essential motion in `@media (prefers-reduced-motion: no-preference)`.
- **Currency and numbers.** Amounts display as ₹ with Indian digit grouping (₹1,23,456.00), right-aligned in tables, tabular numerals. Dates display in a short readable form (e.g. 17 Nov 2026) while stored as ISO text.

## Screen patterns

Details and markup snippets live in `references/patterns.md`. Read the section you need:

- **Forms and validation**: per-field errors with `aria-invalid` + `aria-describedby`, error summary with `role="alert"`, preserved input values, password show/hide toggle.
- **Flash messages**: one shared component in `base.html` using `get_flashed_messages(with_categories=true)`; `role="status"` for success/info, `role="alert"` for errors; dismissible without JS dependence.
- **States**: every data screen needs empty, error, and (if anything is async) loading states. Empty states say what the screen is for and offer the next action.
- **Navigation shell** for logged-in users: Dashboard, Expenses, Add, Profile, Sign out, with `aria-current="page"` and a mobile-friendly layout.
- **Expense list**: table on desktop, cards on mobile; category chips with consistent colors; filter/sort controls that work without JS.
- **Dashboard and charts**: summary tiles, category breakdown as CSS bars or inline SVG, text alternative or data table for every chart, colors not the only differentiator.
- **Destructive actions**: delete uses POST plus a confirmation step (the current stub is a GET, which is unsafe: crawlers and prefetch can trigger it). Reuse and generalize the modal in `main.js`, adding a focus trap.
- **Error pages**: `404.html` and `500.html` extending `base.html` with `@app.errorhandler`.

## Output expectations

- An audit response is a prioritized list, not an essay.
- An implementation response lists files changed and the user-visible effect of each change in one line each.
- Mention any trade-off you made (e.g. "added `--ink-muted` darker value; this slightly changes footer text color").
- Flag anything outside UI scope that you noticed (CSRF is missing; amounts stored as REAL) in one line at the end, without fixing it unasked.
