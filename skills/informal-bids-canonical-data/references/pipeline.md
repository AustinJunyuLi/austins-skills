# Canonical Pipeline

## Canonical entrypoints
- `README.md` is the runbook and command source of truth.
- `scripts/data_canonical/run_pipeline.py` orchestrates the full build.
- `scripts/data_canonical/verify_canonical.py` defines QC checks.
- `Data/DATABASE_GUIDE.md` describes the canonical tables and DuckDB mirror.

## Full rebuild

```bash
python3 -m scripts.data_canonical.run_pipeline \
  --alex-workbook Data/raw/deal_details_Alex_2026.xlsx \
  --chicago-workbook Data/raw/deal_details.xlsx \
  --output-dir Data/canonical
```

## What the pipeline writes
- `Data/canonical/jsonl/raw_rows.jsonl`: immutable workbook rows.
- `Data/canonical/jsonl/deals.jsonl`
- `Data/canonical/jsonl/actors.jsonl`
- `Data/canonical/jsonl/events.jsonl`
- `Data/canonical/jsonl/notes.jsonl`
- `Data/canonical/jsonl/provenance_links.jsonl`
- `Data/canonical/jsonl/estimation_*.jsonl`
- `Data/canonical/jsonl/boundary_triage.jsonl`
- `Data/canonical/jsonl/boundary_auto_candidates.jsonl`
- `Data/canonical/review/boundary_manual_review.csv`
- `Data/canonical/mna_canonical.duckdb`

## Focused verification

```bash
pytest tests/test_canonical_* -v
```

## QC checks to keep in mind
`verify_canonical.py` currently flags:
- missing provenance for events
- advisor misclassification
- grouped-actor flag mismatches
- duplicate canonical events
- formal bids without a formal-boundary event
- executed deals without winner links

## Practical rule
If you change a specific builder under `scripts/data_canonical/`, validate that table's behavior first. Use the full pipeline only after the local transform is stable.
