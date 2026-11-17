# Spendly audit checklist

Work through the sections that apply to the target page. Cite file and selector for every finding.

## 1. Accessibility (WCAG 2.1 AA)
- Contrast: body text 4.5:1, large text and UI component borders 3:1. Check `--ink-faint`, `--ink-muted` on `--paper`/`--paper-warm`, white-on-accent buttons, footer text on the dark footer.
- Focus: every interactive element has a visible `:focus-visible` style. Flag `outline: none` without replacement (currently on `.form-input`).
- Labels: each input has a `<label for>`; placeholders are never the only label.
- Errors: error containers use `role="alert"` (or are inside a live region); invalid inputs have `aria-invalid="true"` and `aria-describedby` pointing at the message.
- Landmarks: one `<main>`, nav has `aria-label`, current page marked with `aria-current="page"`, a skip link exists.
- Keyboard: modals trap focus, close on Esc, restore focus. No hover-only functionality.
- Images/icons: decorative glyphs (◈ ₹) are `aria-hidden="true"`; meaningful ones have text.
- Color is never the only signal (chart categories, error states, required fields).
- Motion: transitions and smooth scrolling are guarded by `prefers-reduced-motion`.

## 2. Design tokens and components
- Grep the CSS for `#[0-9a-fA-F]{3,6}` and `rgb(` outside `:root`. Each hit is a finding.
- Grep templates for `style="` and `<style`. Each hit is a finding (CLAUDE.md).
- Font sizes, spacing, shadows, z-index: are they from a scale or ad hoc?
- Button hierarchy: one primary per view, secondary/ghost for the rest; danger variant for destructive actions. Unused variants are dead code or a missing use.
- Same thing looks the same: cards, badges, inputs share radius/border/padding tokens.

## 3. Forms, feedback, states
- Server validation returns per-field messages, not just one banner. Values preserved on error (except passwords).
- `autocomplete`, `inputmode`, `type`, `min`/`max`/`step` set appropriately (amount: `inputmode="decimal"`).
- Success feedback after actions (flash). Silent redirects are a finding.
- Empty, error and loading states exist for each data view. 404/500 pages exist.
- Submit buttons prevent double-submit where it matters.

## 4. Mobile and responsive
- Check at 360, 375, 768 and 1024px. No horizontal scroll at 360px.
- Tap targets at least 44×44px with spacing; nav links not hidden at small widths.
- Tables convert to cards or are otherwise readable on narrow screens.
- Viewport meta present (it is in `base.html`); inputs at least 16px font to avoid iOS zoom.
- Long text (₹ amounts, descriptions) wraps or truncates deliberately.

## 5. Data display (when relevant)
- ₹ with Indian grouping, right-aligned, tabular numerals; dates short and consistent.
- Charts have a title, a text alternative or data table, legible labels at 375px, and do not rely on color alone.
- Category colors defined once as tokens and reused (chips, bars, legend).

## 6. Content
- Claims are supportable ("Join thousands of people" with no users is a finding for the owner to decide).
- Placeholder copy is realistic and consistent; microcopy says what happens next.
