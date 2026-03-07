---
name: deepthink-review
description: Use when packaging a local codebase into consolidated text files for Gemini Deep Think web review or review follow-up rounds.
---

# Deep Think Review Packaging

## Overview

Use the bundled packager script instead of manually assembling context files. It builds a dated run directory with a consolidated context bundle, prompt, manifest, and upload instructions sized for Deep Think workflows.

## When to Use

- External review of a local repo in Gemini Deep Think
- Follow-up review after local fixes
- Reviews that need text-first packaging rather than a code zip

Do not use this for ordinary local review. Use `code-review` for that.

## Workflow

1. Start at the target repo root.
2. If flags are unclear, run:

```bash
python3 {{SKILLS_ROOT}}/deepthink-review/scripts/pack_for_deepthink.py --help
```

3. Normal packaging flow:

```bash
python3 {{SKILLS_ROOT}}/deepthink-review/scripts/pack_for_deepthink.py \
  --repo . \
  --focus "optional review focus" \
  --strict-freshness
```

4. Read `MANIFEST.md` to confirm what was included and what was omitted by policy or size cap.
5. Paste `PROMPT_deepthink-review.md` and attach the files listed in `UPLOAD.md`.
6. Save the model reply into `MODEL_REPLY.md` inside the run directory before starting the next round.

## Output

The script writes a run directory under:

```text
quality_reports/model_review_artifacts/<timestamp>_deepthink-review/
```

Key files:

- `CONTEXT_deepthink-review.md`
- `PROMPT_deepthink-review.md`
- `MANIFEST.md`
- `UPLOAD.md`
- `MODEL_REPLY.md` if you save a follow-up response

## Important

- Prefer the script over hand-built context bundles.
- Let the script manage freshness checks, attachment selection, and previous-round carryover.
- If artifact freshness warnings appear, fix them before trusting the review pack.
