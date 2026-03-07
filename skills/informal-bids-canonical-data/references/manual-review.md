# Manual Review And Boundary Hygiene

## Boundary triage rule
Canonical events should preserve observed history. Fallback decisions for missing formal boundaries belong in the triage outputs, not as in-place rewrites of canonical events.

## Review artifacts
- `Data/canonical/jsonl/boundary_triage.jsonl`
- `Data/canonical/jsonl/boundary_auto_candidates.jsonl`
- `Data/canonical/jsonl/boundary_manual_review.jsonl`
- `Data/canonical/review/boundary_manual_review.csv`

## Provenance rules
- `raw_row_pk` values are workbook-scoped, so Alex and Chicago rows can coexist.
- Raw workbook columns should remain preserved as imported evidence.
- If a canonical object changes, make sure the provenance link layer still points back to supporting raw rows.

## Grouped actors and unresolved labels
- Keep unresolved or grouped labels explicit.
- Do not invent bidder identities just to satisfy a downstream view.
- Use the review queue when the correct action is human judgment rather than code-side coercion.

## When a task starts from the workbooks
If the task begins with workbook corrections or coding instructions, inspect the canonical outputs after import instead of editing downstream JSONL by hand.
