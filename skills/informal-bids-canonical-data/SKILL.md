---
name: informal-bids-canonical-data
description: Use when the informal_bids repo task involves workbook-to-canonical JSONL or DuckDB conversion, provenance-preserving event normalization, QC fixes, or manual boundary-review updates.
---

# Informal Bids Canonical Data

## Overview
Use this skill for the repository's canonical auction-data layer. The stable workflow is workbook rows -> canonical JSONL tables -> DuckDB mirror -> QC report -> manual review artifacts.

## When to Use
- Use when the task touches `scripts/data_canonical/`, `Data/canonical/`, or canonical test files.
- Use when the change involves workbook import, actor or event normalization, notes, provenance, estimation views, or boundary triage.
- Use when correctness depends on preserving raw workbook semantics and traceability.
- Do not use for BlackJAX runs, Monte Carlo suites, or figure-pack generation. Use `blackjax-mc-suite`.
- Do not use for generic spreadsheet editing outside this pipeline. Use `spreadsheets` or `documents-and-conversion`.

Read [`references/pipeline.md`](./references/pipeline.md) first for entrypoints and output tables.
Read [`references/manual-review.md`](./references/manual-review.md) when the task touches ambiguous boundaries or reviewer-facing artifacts.

## Core Procedure
1. Decide whether the task belongs in raw import, canonical tables, estimation views, or review outputs.
2. Preserve immutable raw rows and workbook-scoped keys before touching any downstream transform.
3. Treat JSONL as the source of truth and DuckDB as a rebuildable mirror.
4. Run the narrowest verification step first, then rerun the full pipeline only if needed.
5. Keep automatic boundary fallbacks separate from canonical event history.

## Common Mistakes
- Editing DuckDB outputs instead of the JSONL-generating code.
- Forcing uncertain formal boundaries directly into canonical events.
- Dropping provenance links while deduplicating or normalizing rows.
- Collapsing grouped actors into fake resolved identities.
- Claiming success without canonical tests or QC checks.
