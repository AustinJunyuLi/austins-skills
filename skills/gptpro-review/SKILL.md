---
name: gptpro-review
description: "Package codebase + artifacts into a zip for GPT Pro web review. Freshness-gated, round-tracked, contamination-free. Produces codebase.zip + PROMPT.md ready to upload."
user_invocable: true
argument-hint: "[optional focus area, e.g. 'validate reward function']"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob", "Bash", "AskUserQuestion"]
---

# GPT Pro Codebase Review Packager

Package the current project into a zip + structured prompt for review by GPT Pro via its web interface.

**Invocation:**
- `/gptpro-review` — full codebase review with default prompt
- `/gptpro-review "focus on X"` — custom focus area injected into prompt

---

## PHASE 1: DISCOVER

1. **Read project identity files** in this order (skip if missing):
   - `CLAUDE.md` (primary — has architecture, commands, design decisions)
   - `README.md`
   - `config/` directory (all `.yaml`, `.yml`, `.toml`, `.json` files)

2. **Build file inventory:**
   ```bash
   # Get directory tree (exclude noise)
   find . -not -path './.git/*' -not -path './.claude/*' -not -path './venv/*' \
          -not -path './__pycache__/*' -not -path './*.egg-info/*' \
          -not -path './node_modules/*' -not -path './data/*' -not -path './.eggs/*' \
          -type f | head -200
   ```

3. **Capture git state:**
   ```bash
   git rev-parse --short HEAD    # snapshot SHA for this round
   git log --oneline -20         # recent history
   git status --short            # uncommitted changes
   ```

4. **Detect round number:**
   - Check if `diagnosis/gptpro/` exists for today's date
   - Count existing `round_N/` directories → this is round `N+1`
   - If round 2+, read `round_{N-1}_reply.md` if it exists
   - If round 2+, find the SHA recorded in the previous round's PROMPT.md

---

## PHASE 2: FRESHNESS CHECKS (HARD GATE)

Before packaging, verify all compiled artifacts are fresh. **Block on any failure.**

### Check 1: LaTeX reports
For each `reports/*.pdf`, find matching `reports/*.tex`:
```bash
# Compare modification times
stat -c %Y reports/stat_arb.pdf
stat -c %Y reports/stat_arb.tex
```
If `.tex` is newer than `.pdf` → **BLOCK**:
> "STALE ARTIFACT: `reports/stat_arb.pdf` is older than `reports/stat_arb.tex` (tex modified YYYY-MM-DD HH:MM, pdf from YYYY-MM-DD HH:MM). Recompile with `pdflatex` before packaging."

### Check 2: R figures
For each `figures/**/*.pdf` or `figures/**/*.png`, find the generating `.R` script in the same directory:
```bash
stat -c %Y figures/stat_arb/equity_curves.pdf
stat -c %Y figures/stat_arb/generate_figures.R
```
If `.R` is newer than any output figure → **BLOCK**:
> "STALE FIGURES: `figures/stat_arb/*.pdf` predate `generate_figures.R`. Re-run `Rscript figures/stat_arb/generate_figures.R`."

### Check 3: Uncommitted changes
```bash
git status --short
```
If there are uncommitted changes → **WARN** (do not block):
> "WARNING: N files have uncommitted changes. The package will reflect the current disk state, not the last commit. Consider committing first."

Proceed only after all BLOCK checks pass.

---

## PHASE 3: PACKAGE ASSEMBLY

### Setup staging directory
```bash
DATE=$(date +%Y-%m-%d)
ROUND=1  # or detected round number
EXPORT_DIR="diagnosis/gptpro/${DATE}/round_${ROUND}"
mkdir -p "${EXPORT_DIR}/codebase"
```

### Copy files into staging
Copy all project files into `${EXPORT_DIR}/codebase/` preserving directory structure.

**INCLUDE:**
- All `src/**/*.py` files
- All `tests/**/*.py` files
- All `scripts/**/*.py` files
- `config/**/*.yaml`, `config/**/*.yml`, `config/**/*.toml`
- `CLAUDE.md`, `README.md`
- `docs/**/*.md` (design docs, plans)
- `reports/**/*.tex`, `reports/**/*.pdf` (source + compiled)
- `figures/**/*.R`, `figures/**/*.pdf`, `figures/**/*.png` (code + outputs)
- `output/**/*.csv`, `output/**/*.json`, `results/**/*.csv`, `results/**/*.json`
- `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt` (if they exist)
- `Makefile`, `justfile` (if they exist)

**EXCLUDE (absolute):**
- `.git/` — version control internals
- `.claude/` — Claude Code meta
- `diagnosis/` — review export packages (recursive packaging)
- `__pycache__/`, `*.pyc`, `.eggs/`, `*.egg-info/` — Python build artifacts
- `venv/`, `.venv/`, `env/` — virtual environments
- `.env`, `*.secret`, `credentials*` — secrets
- `data/` — raw data (too large, not needed for code review)
- `node_modules/` — JS deps
- `*.lock` — lock files
- `*.aux`, `*.log`, `*.synctex.gz`, `*.toc`, `*.out`, `*.fls`, `*.fdb_latexmk` — LaTeX intermediates
- `.worktrees/` — git worktrees
- Any single file > 5MB

### Create zip
```bash
cd "${EXPORT_DIR}" && zip -r codebase.zip codebase/ -x "*.DS_Store"
# Report size
du -sh codebase.zip
```

If zip > 50MB → **BLOCK**: "Zip exceeds 50MB GPT Pro limit. Review exclusions or ask user what to trim."

### Clean up staging
```bash
rm -rf "${EXPORT_DIR}/codebase"  # remove unzipped copy, keep only zip
```

---

## PHASE 4: GENERATE PROMPT

Create `${EXPORT_DIR}/PROMPT.md` with the following structure.

### Prompt Template

```markdown
# Codebase Review Request — [PROJECT_NAME] (Round [N])

**Commit:** [SHORT_SHA] ([DATE])
**Files in package:** [FILE_COUNT] files, [ZIP_SIZE]

## Project Context

[Paste the first ~50 lines of CLAUDE.md or README.md — whichever gives the best overview.
Include the Architecture section if present.]

## File Inventory

[Directory tree of what's in the zip, with brief annotations for key files]

## [ROUND 2+ ONLY] Previous Round Feedback

<details>
<summary>Your analysis from Round [N-1]</summary>

[Verbatim content of round_{N-1}_reply.md]

</details>

## [ROUND 2+ ONLY] Changes Since Round [N-1]

Commit [OLD_SHA] → [NEW_SHA]

[git diff --stat between the two SHAs]

[Abbreviated diff of changed files, truncated if very large]

## Your Task

[If user provided a focus area, insert it here.
Otherwise, use the default below:]

Conduct a thorough review of this codebase. You have the complete source code, configuration, test suite, and compiled report with results.

## Deliverables

### Part 1: Codebase Walkthrough
Explain what this codebase does in plain language. No jargon — if you must use a technical term, define it immediately with a concrete example. Walk through the data flow end-to-end: what goes in, what transformations happen, what comes out. Use specific examples from the code (e.g., "when the agent sees a z-score of 2.1, it does X because Y").

### Part 2: Technical & Theoretical Validation
Meticulously reason through and validate the codebase both technically and theoretically:

(a) **Math ↔ Code correctness:** Do the implementations match the equations in the report? Check every formula.
(b) **Econometric methodology:** Are the cointegration tests, half-life estimation, PCA factor model, and persistence filters correctly specified and implemented?
(c) **RL design choices:** Is the state space sufficient? Is the reward function well-shaped? Are the agent architectures appropriate for this problem?
(d) **Statistical validity:** Is the walk-forward evaluation sound? Are there look-ahead biases? Is the out-of-sample period long enough for inference?
(e) **Bugs & edge cases:** Any silent failures, off-by-one errors, numerical instabilities, or logical errors?

Cross-reference your findings against the included report and results artifacts.

### Part 3: Advancement Roadmap
Provide detailed guidelines to advance the project both theoretically and in implementation:

- For each proposed improvement, provide the **complete mathematical formulation** (not just a name-drop).
- Provide a **concrete code structure / framework** showing where the change fits in the existing architecture.
- Prioritize by expected impact and implementation difficulty.
- Be specific — "use a better model" is not acceptable; "replace linear Q-function with X architecture because Y, with loss function Z" is.
```

### Record SHA for round tracking
Append to PROMPT.md:
```markdown
---
_Internal: snapshot_sha=[SHORT_SHA], round=[N], date=[DATE]_
```

---

## PHASE 5: REPORT TO USER

Print a summary:

```
GPT Pro review package ready (Round N):

  Package:  diagnosis/gptpro/YYYY-MM-DD/round_N/codebase.zip (X.X MB)
  Prompt:   diagnosis/gptpro/YYYY-MM-DD/round_N/PROMPT.md

  Files included: NN files
  Commit: abc1234
  Freshness: all artifacts verified current

  Instructions:
  1. Open chat.openai.com → GPT Pro
  2. Upload codebase.zip
  3. Copy-paste the contents of PROMPT.md as your message
  4. After receiving the response, paste it back and save as:
     diagnosis/gptpro/YYYY-MM-DD/round_N_reply.md
  5. To iterate: patch code locally, then re-invoke /gptpro-review
```

---

## ROUND CONTINUATION PROTOCOL

When the user pastes back a reply from GPT Pro:

1. Save the raw reply to `diagnosis/gptpro/YYYY-MM-DD/round_N_reply.md`
2. **Generate meeting notes** (see MEETING NOTES section below)
3. Inform the user: "Saved Round N reply + meeting notes. Make your local changes, then run `/gptpro-review` to generate Round N+1."

When `/gptpro-review` is invoked and prior rounds exist:

1. Detect the latest round number
2. Read the prior reply file
3. Compute `git diff [old_sha]..HEAD`
4. Include both in the new PROMPT.md under "Previous Round Feedback" and "Changes Since Round N"
5. Package the updated codebase

---

## MEETING NOTES

When the user pastes back a model reply, generate a structured meeting note that distills the feedback into actionable form. This note serves as the record for subsequent brainstorming sessions.

### Output file
`diagnosis/gptpro/YYYY-MM-DD/round_N_meeting_notes.md`

### Template

```markdown
# Meeting Notes: GPT Pro Code Review — Round [N]

**Date:** [YYYY-MM-DD]
**Reviewer:** GPT Pro (OpenAI)
**Project:** [Project name from CLAUDE.md]
**Commit reviewed:** [SHA from PROMPT.md _Internal line]

---

## Executive Summary
[2-3 sentence high-level takeaway from the model's review. What is the overall verdict?]

## Findings by Category

### Correctness Issues (Bugs / Math-Code Mismatches)
[Numbered list. For each item:]
1. **[Short title]** — [Description of the issue]. File: `path/to/file.py`, lines ~N-M.
   - **Severity:** Critical / Major / Minor
   - **Action required:** [Specific fix needed]

### Methodology Concerns (Econometric / Statistical / RL)
[Numbered list. For each item:]
1. **[Short title]** — [Description of the concern and why it matters].
   - **Severity:** Critical / Major / Minor
   - **Action required:** [What to investigate or change]

### Design Observations (Architecture / State Space / Reward)
[Numbered list. Non-critical observations about design choices.]
1. **[Short title]** — [What the model noted and its reasoning].
   - **Recommendation:** [What the model suggests]

### Advancement Proposals
[Numbered list. For each proposed improvement:]
1. **[Short title]**
   - **What:** [Brief description]
   - **Why:** [Expected impact]
   - **Math:** [Key equation or formulation if provided, in LaTeX]
   - **Where in codebase:** [Which files/functions would change]
   - **Effort:** Low / Medium / High
   - **Priority:** P0 (do now) / P1 (next sprint) / P2 (backlog)

## Validated (No Issues Found)
[List aspects the model explicitly confirmed as correct — important for confidence.]

## Open Questions
[Anything the model flagged as uncertain, needing more data, or requiring user judgment.]

## Action Items Summary

| # | Item | Severity | Effort | Priority | Owner |
|---|------|----------|--------|----------|-------|
| 1 | [title] | Critical | Medium | P0 | TBD |
| 2 | [title] | Major | Low | P1 | TBD |
| ... | | | | | |

---
_Raw reply saved to: `round_N_reply.md`_
_Generated by Claude from GPT Pro feedback_
```

### Generation Rules

- **Read the full raw reply carefully** before writing notes — do not summarize superficially
- **Preserve all mathematical formulations** from the model's reply in the meeting notes (use LaTeX)
- **Preserve all specific file/line references** the model made
- **Assign severity** based on impact: Critical = affects correctness of results, Major = affects robustness/validity, Minor = style/improvement
- **Assign priority** based on: P0 = blocks confidence in current results, P1 = meaningful improvement, P2 = nice-to-have
- **Do not editorialize** — report what the model said, not your own assessment. If you disagree with the model, note it in a separate "Claude's Notes" section at the bottom
- **Keep it dense** — this is a working document for brainstorming, not a polished report

---

## IMPORTANT NOTES

- **Never include `diagnosis/` in the zip** — that would create recursive packaging
- **Never include `.claude/`** — Claude Code meta files are not part of the codebase
- **Never include raw data** (`data/` directory) — too large, not needed for review
- **Always verify freshness before packaging** — stale PDFs/figures are the #1 contamination vector
- **Each round is a clean snapshot** — old rounds are preserved for audit trail but never mixed into new packages
