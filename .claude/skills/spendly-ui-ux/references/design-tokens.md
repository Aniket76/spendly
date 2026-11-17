# Spendly design tokens

Source of truth: the `:root` block at the top of `static/css/style.css`. Re-read it before editing, since it may have changed. Current values at the time this skill was written:

| Token | Value | Use |
|---|---|---|
| `--ink` | #0f0f0f | primary text |
| `--ink-soft` | #2d2d2d | secondary text |
| `--ink-muted` | #6b6b6b | tertiary text (about 5:1 on paper, OK for text) |
| `--ink-faint` | #a0a0a0 | decorative only; fails contrast for text |
| `--paper` / `--paper-warm` / `--paper-card` | #f7f6f3 / #f0ede6 / #fff | backgrounds |
| `--accent` / `--accent-light` | #1a472a / #e8f0eb | brand green, primary actions |
| `--accent-2` / `--accent-2-light` | #c17f24 / #fdf3e3 | amber highlights |
| `--danger` / `--danger-light` | #c0392b / #fdecea | errors, destructive |
| `--border` / `--border-soft` | #e4e1da / #eeebe4 | dividers (decorative borders are exempt from 3:1; input borders are not) |
| `--font-display` / `--font-body` | DM Serif Display / DM Sans | headings / everything else |
| `--radius-sm/md/lg` | 6 / 12 / 20px | corners |

## Tokens to add when needed (follow these names)

- Spacing scale: `--space-1` 4px, `--space-2` 8px, `--space-3` 12px, `--space-4` 16px, `--space-6` 24px, `--space-8` 32px, `--space-12` 48px.
- Type scale: `--text-xs` .75rem, `--text-sm` .875rem, `--text-base` 1rem, `--text-lg` 1.125rem, `--text-xl` 1.5rem, `--text-2xl` 2rem.
- Shadows: `--shadow-sm`, `--shadow-md` (soft, warm, low opacity black).
- Focus ring: `--focus-ring: 0 0 0 3px` plus accent at partial opacity, or `outline: 2px solid var(--accent); outline-offset: 2px`.
- Success and info colors if flash messages need them (`--success`, `--success-light`), chosen to meet AA on their light backgrounds.
- Category palette: `--cat-food`, `--cat-transport`, `--cat-bills`, `--cat-shopping`, `--cat-health`, `--cat-other`, each with enough contrast against white for chips (text on tinted background >= 4.5:1).

## Rules for changing a token

- Changing an existing token value changes every page. Say so in your report, and check the places it is used (grep `var(--name)`).
- Prefer adding a new token over silently darkening an old one, unless the old one is an accessibility failure, in which case fix it and report it.
- Verify contrast numerically for any new text/background pair instead of eyeballing. A short Python snippet using the WCAG relative luminance formula is enough.
