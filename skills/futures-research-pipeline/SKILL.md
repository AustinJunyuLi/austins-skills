---
name: futures-research-pipeline
description: Use when working on commodity futures research with minute-bar ingestion, exchange calendars and timezones, deterministic F1..F12 curves, roll logic, or walk-forward backtests.
---

# Futures Research Pipeline

## Overview

Use this for the shared futures stack across deterministic curve construction, daily factor research, and RL or stat-arb work on commodity futures panels.

## When to Use

- Minute-bar ingestion, file scanning, or timezone inference
- CME calendar or trade-date boundary issues
- Expiry-ranked curve construction, spreads, or roll detection
- DTE or BTE analysis, event studies, or robustness checks
- Walk-forward backtests on futures data

Do not use this for simple external data pulls with no local futures pipeline work; use `finance-data` instead.

## First Pass

1. Identify the repo family from [`references/repos.md`](./references/repos.md).
2. Read only the subsection for that repo.
3. Before editing logic, check the invariants in [`references/workflows.md`](./references/workflows.md).

## Core Rules

- Keep contract labels expiry-based, never liquidity-based, unless the repo explicitly says otherwise.
- Keep `US/Central` normalization and the 17:00 CT trade-date boundary explicit.
- Treat back-adjusted or Panama-style prices as signal inputs only when the repo already does so; preserve tradable return logic for PnL.
- Enforce no-lookahead in roll logic, feature generation, and walk-forward evaluation.
- Prefer targeted tests before full pipeline runs.

## Common Mistakes

- Mixing liquidity migration with front-contract labeling
- Forward-filling away roll or missing-print information
- Using generated outputs as the source of truth instead of config, pipeline code, and tests
