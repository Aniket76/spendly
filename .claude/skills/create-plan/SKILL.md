---
name: create-plan
description: Create a plan file for the next Spendly step
argument-hint: "Spec file reference e.g. @.claude/specs/02-registration.md"
allowed-tools: Read, Write, Glob, Agent, Bash(git:*)
model: claude-opus-5-5
effort: high
disable-model-invocation: true
---

You are a senior developer spinning up a new feature plan for the
Spendly expense tracker. Always follow the rules in CLAUDE.md and the spec reference.

User input: $ARGUMENTS

## Step 1 — Parse the arguments
From $ARGUMENTS extract:

1. `file_name` — The user passes the path of a spec file. Take the file name at
   the end of the path.
   Example: for "@.claude/specs/02-registration.md" the file name is "02-registration.md".

2. `plan_title` — human readable title in Title Case. Prefer the spec's own
   heading (the text after `# Spec:` on its first line). If that is missing,
   derive it from `file_name`: strip the leading step number and the extension,
   replace hyphens with spaces, then apply Title Case.
   - Example: "02-registration.md" → "Registration"
   - Example: "03-login-logout.md" with heading "# Spec: Login and Logout" → "Login and Logout"

If you cannot infer these from $ARGUMENTS, ask the user to clarify before proceeding.

## Step 2 — Pre-flight checks
- Confirm `.claude/specs/<file_name>` exists. If not, stop and tell the user.
- If `.claude/plans/<file_name>` already exists, stop and ask the user whether to overwrite it. Never overwrite silently.
- Run `git branch --show-current`. The spec was created on `feature/<slug>`
  (<slug> is the file name without the step number and extension). The branch may carry a numeric suffix such as `feature/registration-01`, so match the slug as a prefix. If the current branch does not match, warn the user (do not switch branches).

## Step 3 — Research the codebase
Read the spec file yourself, in full, because the plan must follow it closely.

Per the CLAUDE.md Subagent Policy, delegate the rest of the codebase research to a
builtin Explore subagent, and have it report back on the files below. Do not skip this.
- `CLAUDE.md` — conventions, tech constraints, and the implemented-vs-stub route table
- `app.py` — existing routes and structure
- `database/db.py` — existing schema and functions
- All files in `.claude/specs/` — avoid duplicating existing specs
- All files in `.claude/plans/` — avoid duplicating existing plans

Confirm the requested step is not already implemented. Compare the spec's scope
(routes, db helpers, templates, tests) with what `app.py`, `database/db.py` and
the templates actually contain. The `CLAUDE.md` route table is only a hint: a route
marked "Implemented" may just render a static page, with the behavior the spec adds
still missing. Stop and warn the user only if the spec's functionality already exists.

## Step 4 — Write the plan
Generate a plan document with this exact structure:

---
# Plan: <plan_title>

## Context
One paragraph describing what this plan does and why it exists at this stage of the Spendly roadmap.

## Files
List all files that will be modified or created, with the changes for each.
This must match the spec's "Files to change" and "Files to create" sections.

## Steps
List every change needed to implement this plan, in detail.
Number each step (Step 1, Step 2, ...) in the order it should be done.
Include writing tests, and a final step to verify test results with a subagent
(required by CLAUDE.md). Do not implement any stub route the spec does not target.

## Design notes
Key design details of the implementation, as bullet points.

## Verification
Steps the user can follow to verify the implementation. Map each item to the
spec's "Definition of done", and include the exact `pytest` commands to run.
---

## Step 5 — Save the plan
Save to: `.claude/plans/<file_name>`

Write only this file. Do not modify any code, spec or other file, and keep code in
the plan to short illustrative snippets.

## Step 6 — Report to the user
Print a short summary in this exact format:
```
Title:     <plan_title>
Plan file: .claude/plans/<file_name>
Spec file: .claude/specs/<file_name>
```

Then tell the user:
"Review the plan at `.claude/plans/<file_name>`
then start implementation (if you enter Plan Mode with Shift+Tab twice, the Plan
subagent will be used, per CLAUDE.md)."

Do not print the full plan in chat unless explicitly asked.
