# Spendly screen patterns

Snippets are starting points. Match existing class naming (`.form-group`, `.form-input`, `.auth-*`, `.btn-*`) and tokens.

## Contents
1. Form field with error
2. Flash messages
3. Logged-in navigation
4. Expense list (table to cards)
5. Dashboard tiles and CSS bar chart
6. Confirm dialog for delete
7. Error pages

## 1. Form field with error

```html
<div class="form-group">
    <label for="email">Email address</label>
    <input type="email" id="email" name="email" class="form-input"
           autocomplete="email" value="{{ email or '' }}" required
           {% if errors and errors.email %}aria-invalid="true" aria-describedby="email-error"{% endif %}>
    {% if errors and errors.email %}
    <p class="field-error" id="email-error">{{ errors.email }}</p>
    {% endif %}
</div>
```
Route side: validation returns a dict of field to message (keep the logic in a helper, route just passes `errors`). Use `autocomplete="new-password"` on register and `current-password` on login. Show/hide password is a small vanilla JS toggle on a `<button type="button" aria-pressed>`; the form must still work without JS.

## 2. Flash messages

In `base.html`, inside `<main>` before the content block:
```html
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
  <div class="flash-stack">
    {% for category, message in messages %}
    <div class="flash flash-{{ category }}" role="{{ 'alert' if category == 'error' else 'status' }}">{{ message }}</div>
    {% endfor %}
  </div>
  {% endif %}
{% endwith %}
```
Routes call `flash("Account created. Please sign in.", "success")`. Needs `app.secret_key` already set. Replaces one-off banners like `.auth-error` over time.

## 3. Logged-in navigation

Show Dashboard, Expenses, Add expense, Profile, Sign out when `session.get("user_id")`. Mark the current page using `request.endpoint` to set `aria-current="page"`. On narrow screens use a wrapping or scrollable row of links with 44px targets, or a `<details>`-based menu, which needs no JS and is keyboard accessible. Never remove the primary auth action at small widths.

## 4. Expense list

Desktop: `<table>` with `<caption class="sr-only">`, `<th scope="col">`, amount column right-aligned with `font-variant-numeric: tabular-nums`. Mobile: below 640px, restyle rows as cards using `display:block` on `tr` and `data-label` attributes on `td` shown via `td::before { content: attr(data-label) }`. Category as a chip: colored background tint plus the category text (never color alone). Empty state: icon-free, a sentence, and a primary "Add your first expense" button.

## 5. Dashboard tiles and CSS bar chart

Tiles: total this month, top category, count, daily average, each a card with a muted label and a large display-font value.

CSS bar chart without inline styles: set the width through a class from a small bucketed set, or emit an inline SVG in the template with computed `width` attributes (attributes are not `style=`). Each bar row has the category name, value in ₹, and percentage as text. Provide the same data as a visually hidden table when the chart is the only way to see it.

## 6. Confirm dialog for delete

Delete must be POST (`<form method="post">` with a button). Use a `<dialog>` element or the existing modal pattern from `main.js`, generalized with `data-confirm-open` / `data-confirm-close`, a focus trap (Tab cycles inside), Esc to close, focus restored to the trigger. Dialog text names the item and amount: "Delete ₹450.00 for Lunch on 17 Nov?". Danger-styled confirm button, neutral cancel.

## 7. Error pages

`templates/404.html` and `500.html` extend `base.html`, with a heading, one sentence, and a button back to the dashboard (or landing when logged out). Register with `@app.errorhandler(404)` returning `render_template(...), 404`.
