---
name: econ-theory-paper-numerics
description: Use when a theory paper combines numerical solvers or calibration with paper-facing figures, tables, and LaTeX manuscript updates.
---

# Econ Theory Paper Numerics

## Overview

Use this for theory projects where numerical code, paper artifacts, and manuscript files must stay synchronized.

## When to Use

- Solver or calibration changes that affect paper-facing results
- Comparative statics, export tables, or figure regeneration
- LaTeX manuscript updates driven by numerical outputs
- Smoke, fast, or paper-profile output generation

Do not use this for pure writing-only edits with no numerical workflow; use `research-writing` instead.

## First Pass

1. Read [`references/blockholder.md`](./references/blockholder.md).
2. Identify the paper-facing entrypoint and target output.
3. Use [`references/output-sync.md`](./references/output-sync.md) before editing.

## Core Rules

- Never hand-edit generated figures or tables as the long-term fix.
- Use the smallest profile that answers the question before running expensive profiles.
- Keep the manuscript, exported artifacts, and numerical source aligned.
- Re-run tests or smoke commands before claiming that a numerical change is safe.

## Common Mistakes

- Editing derived outputs instead of the generating code
- Jumping straight to high-resolution runs when a smoke profile would catch the issue
- Updating the paper text without regenerating the affected artifacts
