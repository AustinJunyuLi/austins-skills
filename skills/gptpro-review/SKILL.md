---
name: gptpro-review
description: Use when packaging a local codebase and fresh artifacts for GPT Pro web review or follow-up review rounds.
---

# GPT Pro Review Packaging

## Overview

Use the bundled packager script instead of assembling uploads by hand. It creates a dated run directory with a zip bundle, prompt, manifest, and upload instructions.

## When to Use

- External review of a local repo in GPT Pro
- Follow-up review after local changes
- Codebase audits that need a clean snapshot plus fresh artifacts

Do not use this for normal local code review. Use `code-review` for that.

## Workflow

1. Start at the target repo root.
2. If flags are unclear, run:

```bash
python3 {{SKILLS_ROOT}}/gptpro-review/scripts/pack_for_gptpro.py --help
```

3. Normal packaging flow:

```bash
python3 {{SKILLS_ROOT}}/gptpro-review/scripts/pack_for_gptpro.py \
  --repo . \
  --focus "optional review focus" \
  --strict-freshness
```

4. Read the generated `MANIFEST.md` before uploading.
5. Upload `repo_bundle.zip`, then paste `PROMPT_gptpro-review.md`.
6. Save the model reply into `MODEL_REPLY.md` inside the run directory before starting the next round.

## Output

The script writes a run directory under:

```text
quality_reports/model_review_artifacts/<timestamp>_gptpro-review/
```

Key files:

- `repo_bundle.zip`
- `PROMPT_gptpro-review.md`
- `MANIFEST.md`
- `UPLOAD.md`
- `MODEL_REPLY.md` if you save a follow-up response

## Important

- Prefer the script over manual zipping.
- Let the script own freshness checks, manifest generation, and round tracking.
- If the repo has stale PDFs or figures, fix them before trusting the package.
