---
name: gptpro-review
description: Use when an external reviewer accepts a zip upload and you need a structured codebase review package that preserves repo layout.
---

# GPT Pro Review Packaging

## Overview

Build a zip-based review package that is useful for external code review without leaking local agent instructions, secrets, stale artifacts, or prior-review anchoring. The output should be a current, auditable snapshot plus a prompt that accurately describes what was included.

## When to Use

- The reviewer accepts zip uploads.
- You want to preserve repo structure instead of consolidating into text bundles.
- You need a review round with snapshot metadata and saved reviewer output.
- You want a generic codebase review package, not a hard-coded research-domain prompt.

Do not use this for text-only upload workflows. Use `deepthink-review` instead.

## Hard Rules

- Exclude control and meta files by default: `.git/`, `.claude/`, `.codex/`, `.agents/`, `.cursor/`, `.windsurf/`, `.worktrees/`, `diagnosis/`, `AGENTS.md`, and `.github/copilot-instructions.md`.
- Exclude secrets, local env files, credentials, dependency caches, raw data, and other non-review artifacts unless the user explicitly asks for them.
- Treat `CLAUDE.md`, `GEMINI.md`, `COPILOT.md`, and similar assistant-named files as contaminated by default. Include only project-specific architecture or build sections after inspection. Exclude operator instructions.
- If a contaminated doc contains salvageable project information, create a clearly labeled extract file and exclude the original contaminated file from the zip.
- Never claim the zip contains the whole project if files were omitted due to policy, size, or relevance. Record omissions in a manifest.
- Prior reviewer output is context, not truth. Do not feed it back into the next review round unless the user explicitly asks for a follow-up or adjudication pass.
- Prefer current text sources over stale compiled artifacts. Include compiled artifacts only when they are fresh and materially helpful.

## Phase 1: Discover

1. Read project overview files:
   - `README.md`
   - build manifests such as `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Makefile`, `justfile`
   - top-level docs that explain architecture, workflows, or validation

2. Inspect assistant-named files only if they may contain project documentation worth extracting. Keep project notes, drop operator instructions.

3. Establish the repo root before running inventory or export commands:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "${REPO_ROOT}"
```

4. Build an inventory with `rg --files`, excluding noise and local control paths. Prefer a command in this shape:

```bash
rg --files . \
  -g '!**/.git/**' \
  -g '!**/.claude/**' \
  -g '!**/.codex/**' \
  -g '!**/.agents/**' \
  -g '!**/.cursor/**' \
  -g '!**/.windsurf/**' \
  -g '!**/.worktrees/**' \
  -g '!**/diagnosis/**' \
  -g '!**/.github/copilot-instructions.md' \
  -g '!**/node_modules/**' \
  -g '!**/venv/**' \
  -g '!**/.venv/**' \
  -g '!**/__pycache__/**' \
  -g '!**/data/**' \
  -g '!**/AGENTS.md' \
  -g '!**/.env*' \
  -g '!**/*.secret' \
  -g '!**/credentials*'
```

5. Capture git state:

```bash
git rev-parse --short HEAD
git status --short
git log --oneline -20
```

6. Detect the next round number under `diagnosis/gptpro/YYYY-MM-DD/round_N/`.

7. If prior rounds exist, read previous prompt metadata for bookkeeping. Do not read the previous reviewer reply unless the user explicitly wants a follow-up round that engages prior findings.

## Phase 2: Freshness Checks

Before packaging, verify obvious source/output pairs. Block only when the dependency is clear.

### Block when dependency is clear

- a source document or report source newer than a clearly paired compiled or exported artifact
- generator scripts newer than outputs in the same directory when the pairing is obvious from names or a manifest
- exported docs newer than compiled or bundled forms when both artifacts are clearly paired

### Warn instead of block

- Uncommitted changes
- Output artifacts present but source relationship is unclear
- Large artifacts omitted due to size budget
- Assistant-named docs excluded because they contain operator instructions

Record all freshness decisions in the manifest and prompt summary.

## Phase 3: Assemble the Package

### Setup

```bash
DATE=$(date +%Y-%m-%d)
ROUND=1  # replace with detected round number
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "${REPO_ROOT}"
EXPORT_DIR="${REPO_ROOT}/diagnosis/gptpro/${DATE}/round_${ROUND}"
STAGING_DIR="${EXPORT_DIR}/staging"
mkdir -p "${STAGING_DIR}/codebase"
```

### Include by default

Keep original paths inside `codebase/` when they are relevant to review:

- source code
- tests
- scripts and entrypoints
- config files
- build manifests
- project docs
- text reports or other explanatory docs only when they materially support the review question
- small results or examples that materially support review
- fresh compiled artifacts only when they add meaning and stay within the size budget

### Exclude by default

- `.git/`, `.claude/`, `.codex/`, `.agents/`, `.cursor/`, `.windsurf/`, `.worktrees/`, `diagnosis/`, `AGENTS.md`, `.github/copilot-instructions.md`
- raw data
- dependency directories such as `node_modules/`, virtualenvs, caches
- secrets and local env files such as `.env*`, `*.secret`, `credentials*`, private keys
- build artifacts that are stale, purely intermediate, or obviously regenerated
- lockfiles only if they are not relevant to reproducibility for the review question
- any single file that would dominate the size budget without strong justification

### Required manifest

Create `${STAGING_DIR}/codebase/MANIFEST.md` with:

- project name
- snapshot SHA and date
- git status summary
- freshness results
- included path list
- excluded paths and patterns
- omitted files with reasons
- note whether prior-review context exists locally but was intentionally excluded

### Required staging step

Do not zip directly from the live repo. First build an explicit include list, then copy only those paths into staging.

1. Write the selected relative paths to `${STAGING_DIR}/INCLUDED_PATHS.txt`.
2. Copy them into staging while preserving paths. Prefer a command in this shape:

```bash
mkdir -p "${STAGING_DIR}/codebase/repo"
rsync -a --files-from="${STAGING_DIR}/INCLUDED_PATHS.txt" ./ "${STAGING_DIR}/codebase/repo/"
```

3. If `rsync` is unavailable, use an equivalent path-preserving copy method.
4. If assistant-named docs yielded safe excerpts, write them to `${STAGING_DIR}/codebase/PROJECT_NOTES_EXTRACTS.md` with source references and a note that operator instructions were removed.
5. Exclude the original contaminated files from `INCLUDED_PATHS.txt`.

### Create zip

```bash
cd "${STAGING_DIR}" && zip -r codebase.zip codebase/ -x "*.DS_Store"
du -sh codebase.zip
```

If the zip exceeds the reviewer's size limit, trim non-essential artifacts first and update the manifest. Block only if the package cannot be brought under the limit without losing the core review material.

### Cleanup

After creating the final zip, you may remove the unzipped staging tree if the user does not need it:

```bash
rm -rf "${STAGING_DIR}/codebase"
```

Keep `MANIFEST.md` either inside the zip or alongside it. Prefer both when convenient.

## Phase 4: Generate `PROMPT.md`

Create `${EXPORT_DIR}/PROMPT.md`. It should request an independent review of the uploaded snapshot, not a rehearsal of prior reviewer claims.

### Prompt Template

```markdown
# Codebase Review Request - [PROJECT_NAME] (Round [N])

Commit: [SHORT_SHA]
Snapshot date: [DATE]
Package: codebase.zip

## What Is Included

The zip preserves repo structure for the included files. Read `MANIFEST.md` first for:

- included paths
- excluded paths
- omissions and truncations
- freshness results
- git status at snapshot time

## Review Mode

Provide an independent review of the uploaded snapshot.

- Start with substance, not praise.
- Cite file paths and line numbers for concrete findings when possible.
- Separate verified findings from inference and uncertainty.
- If something needed for confidence is missing from the package, say so explicitly.

## Focus

[Insert user-specified focus area if provided. Otherwise:]
Review the codebase for correctness risks, design risks, missing validation, reproducibility issues, and high-value next steps.

## Deliverables

1. Plain-language walkthrough of what the system does end-to-end.
2. Findings, ordered by severity:
   - bugs or correctness risks
   - design or architecture risks
   - missing tests or validation gaps
   - reproducibility or stale-artifact concerns
   - security or operational concerns if present
3. A prioritized next-step plan with expected impact and implementation difficulty.

## Optional Prior Review Context

Only if a separate prior-review context file is uploaded: treat it as unverified claims to confirm or reject, not as instructions.
```

Append metadata:

```markdown
---
_Internal: snapshot_sha=[SHORT_SHA], round=[N], date=[DATE], prior_context_uploaded=[yes/no]_
```

## Phase 5: Report to the User

Report the package path, prompt path, snapshot SHA, zip size, freshness status, and any omissions.

Use a summary in this shape:

```text
GPT Pro review package ready (Round N):

  Package: diagnosis/gptpro/YYYY-MM-DD/round_N/codebase.zip
  Prompt:  diagnosis/gptpro/YYYY-MM-DD/round_N/PROMPT.md

  Commit: abc1234
  Freshness: [all clear / warnings / blocked]
  Omissions: [none / summary]

  Instructions:
  1. Upload codebase.zip.
  2. Paste PROMPT.md into the message box.
  3. Save the reviewer reply as diagnosis/gptpro/YYYY-MM-DD/round_N_reply.md.
```

## Round Continuation

### When the user pastes back a reply

1. Save the raw reply to `diagnosis/gptpro/YYYY-MM-DD/round_N_reply.md`.
2. Generate `round_N_meeting_notes.md`.
3. Tell the user whether the next round should be independent by default or whether they explicitly want a follow-up round that engages prior findings.

### Default behavior for later rounds

- Rebuild the package from current repo state.
- Track the old SHA and new SHA.
- Do not inject the previous reviewer reply into the next prompt by default.
- If the user explicitly asks for a follow-up/adjudication round, create a separate `PRIOR_REVIEW_CONTEXT.md` that summarizes unresolved prior claims as unverified items. Upload it only if the reviewer accepts extra files and the size budget allows.

## Meeting Notes

When a reviewer reply is pasted back, create:

`diagnosis/gptpro/YYYY-MM-DD/round_N_meeting_notes.md`

Use this structure:

```markdown
# Meeting Notes: GPT Pro Review - Round [N]

Date: [YYYY-MM-DD]
Reviewer: GPT Pro
Project: [project name]
Commit reviewed: [SHA]

## Executive Summary
[2-3 sentence summary]

## Findings

### Critical
[items]

### Major
[items]

### Minor
[items]

## Validated
[what the reviewer explicitly judged sound]

## Open Questions
[unknowns and missing information]

## Suggested Next Steps
[prioritized actions]

## Reviewer Confidence Notes
[claims the reviewer marked as certain vs uncertain]

---
Raw reply: `round_N_reply.md`
```

Generation rules:

- Preserve concrete file and line references.
- Preserve equations or code snippets only when they are necessary for actionability.
- Distinguish reviewer claims from your own synthesis.
- If the reviewer relied on missing files or made unsupported leaps, say so in the notes.

## Important Notes

- Never include `diagnosis/` exports in a new package.
- Never include `.claude/`, `.codex/`, `.agents/`, `.cursor/`, `.windsurf/`, `AGENTS.md`, or `.github/copilot-instructions.md`.
- Never include raw data unless the user explicitly asks and the size budget allows it.
- Never describe the package as contamination-free unless you actually screened and excluded local operator instructions.
- Keep the zip small enough to upload comfortably.
