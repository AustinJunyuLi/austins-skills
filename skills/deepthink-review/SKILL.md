---
name: deepthink-review
description: "Package codebase into consolidated text files for Gemini Deep Think web review. Max 10 files, text-only. Freshness-gated, round-tracked, contamination-free."
user_invocable: true
argument-hint: "[optional focus area, e.g. 'validate cointegration methodology']"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob", "Bash", "AskUserQuestion"]
---

# Gemini Deep Think Codebase Review Packager

Package the current project into consolidated text files + structured prompt for review by Gemini Deep Think via its web interface.

**Constraints:** Deep Think accepts up to ~10 file uploads, text-only (no binary PDFs/PNGs). All content must be consolidated into readable markdown files.

**Invocation:**
- `/deepthink-review` — full codebase review with default prompt
- `/deepthink-review "focus on X"` — custom focus area injected into prompt

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

3. **Read ALL source files** — you need to understand the full codebase to consolidate intelligently. Read every `.py`, `.R`, `.tex`, `.yaml` file.

4. **Capture git state:**
   ```bash
   git rev-parse --short HEAD    # snapshot SHA for this round
   git log --oneline -20         # recent history
   git status --short            # uncommitted changes
   ```

5. **Detect round number:**
   - Check if `diagnosis/deepthink/` exists for today's date
   - Count existing `round_N/` directories → this is round `N+1`
   - If round 2+, read `round_{N-1}_reply.md` if it exists
   - If round 2+, find the SHA recorded in the previous round's PROMPT.md

---

## PHASE 2: FRESHNESS CHECKS (HARD GATE)

Before packaging, verify all compiled artifacts are fresh. **Block on any failure.**

### Check 1: LaTeX reports
For each `reports/*.pdf`, find matching `reports/*.tex`:
```bash
stat -c %Y reports/stat_arb.pdf
stat -c %Y reports/stat_arb.tex
```
If `.tex` is newer than `.pdf` → **BLOCK**:
> "STALE ARTIFACT: `reports/stat_arb.pdf` is older than `reports/stat_arb.tex`. Recompile before packaging."

### Check 2: R figures
For each `figures/**/*.R` script, check if any generated output is older:
```bash
stat -c %Y figures/stat_arb/equity_curves.pdf
stat -c %Y figures/stat_arb/generate_figures.R
```
If `.R` is newer than any output figure → **BLOCK**:
> "STALE FIGURES: Figure outputs predate R script. Re-run Rscript."

### Check 3: Uncommitted changes
```bash
git status --short
```
If uncommitted changes → **WARN** (do not block):
> "WARNING: N files uncommitted. Package reflects disk state, not last commit."

Proceed only after all BLOCK checks pass.

---

## PHASE 3: CONSOLIDATE INTO TEXT FILES

### Setup staging directory
```bash
DATE=$(date +%Y-%m-%d)
ROUND=1  # or detected round number
EXPORT_DIR="diagnosis/deepthink/${DATE}/round_${ROUND}"
mkdir -p "${EXPORT_DIR}"
```

### File 1: `00_PROJECT_OVERVIEW.md`

Consolidate project-level context:

```markdown
# Project Overview

## CLAUDE.md
[Full contents of CLAUDE.md]

## README.md
[Full contents of README.md, if it exists]

## Git History (last 20 commits)
[Output of git log --oneline -20]

## Directory Tree
[Full project tree, excluding .git/, __pycache__/, venv/, data/, .claude/]

## Build Configuration
[Contents of pyproject.toml, setup.py, setup.cfg, requirements.txt — whichever exist]
```

### File 2: `01_CONFIG.md`

```markdown
# Configuration Files

## config/default.yaml
[Full contents]

## [Any other config files, each with a header]
```

### File 3: `02_DATA_PIPELINE.md`

Concatenate data loading and feature engineering modules:

```markdown
# Data Pipeline

## src/rl_trade/data.py
[Full contents]

## src/rl_trade/features.py
[Full contents]

## [Any other data-related modules]
```

### File 4: `03_CORE_LOGIC.md`

Concatenate environments, agents, and core algorithms:

```markdown
# Core Logic

## src/rl_trade/environment.py
[Full contents — or spread_trading_env.py if stat-arb]

## src/rl_trade/agent_base.py
[Full contents]

## src/rl_trade/linear_sarsa.py
[Full contents]

## src/rl_trade/reinforce_agent.py
[Full contents]

## src/rl_trade/agent_factory.py
[Full contents]

## [Any other agent/environment modules — cointegration.py, portfolio.py, etc.]
```

**Grouping rule:** If the project has many modules, group by functional area. If a single file exceeds ~2000 lines, include the most important sections with `[... N lines omitted, handles X ...]` markers.

### File 5: `04_EVALUATION.md`

```markdown
# Evaluation & Baselines

## src/rl_trade/evaluation.py
[Full contents]

## src/rl_trade/baselines.py
[Full contents]

## src/rl_trade/walkforward.py
[Full contents]
```

### File 6: `05_TESTS.md`

```markdown
# Test Suite

## tests/test_[most important].py
[Full contents of 2-3 most relevant test files]

## Test Summary
[For remaining test files: file name, number of tests, what they cover — 1-2 lines each]
```

**Size control:** If the test suite is very large, include only the most important test files in full. Summarize the rest with names and brief descriptions.

### File 7: `06_REPORT.md`

```markdown
# Report (LaTeX Source)

This is the LaTeX source for the compiled PDF report. It contains the methodology,
equations, results tables, and figure references.

## reports/stat_arb.tex
[Full contents of the .tex file]

Note: The compiled PDF includes figures generated by the R scripts in File 08.
Cross-reference figure labels (e.g., \ref{fig:equity}) with the R code.
```

### File 8: `07_FIGURES_AND_SCRIPTS.md`

```markdown
# Figure Generation & Entry Points

## figures/stat_arb/generate_figures.R
[Full contents]

## scripts/run_dqn.py
[Full contents — or whatever the main entry point is]

## [Any other scripts]
```

### File 9: `08_SUPPORTING.md`

Catch-all for anything not covered above:

```markdown
# Supporting Files

## [Any remaining .py, .md, .yaml files not included in files 01-08]
[Full contents with clear headers]
```

**If nothing remains**, this file can contain:
```markdown
# Supporting Files
All project files have been included in files 00-07. No additional files.
```

### Consolidation Rules

- **Every included file gets a clear `## path/to/file.py` header** so the model can trace back
- **No binary content** — PDFs, PNGs, images are replaced by their source (`.tex`, `.R`)
- **Preserve all code exactly** — no summarization of source code unless a single file exceeds ~2000 lines
- **UTF-8 text only**

---

## PHASE 4: GENERATE PROMPT

Create `${EXPORT_DIR}/PROMPT.md` (this is file 10 — the one you copy-paste as your message).

### Prompt Template

```markdown
# Codebase Review Request — [PROJECT_NAME] (Round [N])

**Commit:** [SHORT_SHA] ([DATE])
**Files uploaded:** 9 consolidated files covering [FILE_COUNT] source files

## How to Read the Uploaded Files

| File | Contents |
|------|----------|
| 00_PROJECT_OVERVIEW.md | CLAUDE.md, README, git history, directory tree, build config |
| 01_CONFIG.md | All YAML/TOML configuration |
| 02_DATA_PIPELINE.md | Data loading, feature engineering |
| 03_CORE_LOGIC.md | Environments, agents, algorithms |
| 04_EVALUATION.md | Metrics, baselines, walk-forward validation |
| 05_TESTS.md | Test suite (key files in full, rest summarized) |
| 06_REPORT.md | LaTeX source of the results report |
| 07_FIGURES_AND_SCRIPTS.md | R figure code, entry-point scripts |
| 08_SUPPORTING.md | Any remaining files |

Each file contains concatenated source with `## path/to/file` headers.
The LaTeX report (06) references figures generated by the R code in (07).

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

Conduct a thorough review of this codebase. You have the complete source code, configuration, test suite, and report with results (as LaTeX source).

## Deliverables

### Part 1: Codebase Walkthrough
Explain what this codebase does in plain language. No jargon — if you must use a technical term, define it immediately with a concrete example. Walk through the data flow end-to-end: what goes in, what transformations happen, what comes out. Use specific examples from the code (e.g., "when the agent sees a z-score of 2.1, it does X because Y").

### Part 2: Technical & Theoretical Validation
Meticulously reason through and validate the codebase both technically and theoretically:

(a) **Math ↔ Code correctness:** Do the implementations match the equations in the report (file 06)? Check every formula.
(b) **Econometric methodology:** Are the cointegration tests, half-life estimation, PCA factor model, and persistence filters correctly specified and implemented?
(c) **RL design choices:** Is the state space sufficient? Is the reward function well-shaped? Are the agent architectures appropriate for this problem?
(d) **Statistical validity:** Is the walk-forward evaluation sound? Are there look-ahead biases? Is the out-of-sample period long enough for inference?
(e) **Bugs & edge cases:** Any silent failures, off-by-one errors, numerical instabilities, or logical errors?

Cross-reference your findings against the report source (file 06) and the actual implementation code.

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
Gemini Deep Think review package ready (Round N):

  Directory: diagnosis/deepthink/YYYY-MM-DD/round_N/
  Files:
    00_PROJECT_OVERVIEW.md    (XX KB)
    01_CONFIG.md              (XX KB)
    02_DATA_PIPELINE.md       (XX KB)
    03_CORE_LOGIC.md          (XX KB)
    04_EVALUATION.md          (XX KB)
    05_TESTS.md               (XX KB)
    06_REPORT.md              (XX KB)
    07_FIGURES_AND_SCRIPTS.md (XX KB)
    08_SUPPORTING.md          (XX KB)
    PROMPT.md                 (XX KB)

  Total: 10 files, XX KB
  Commit: abc1234
  Freshness: all artifacts verified current

  Instructions:
  1. Open gemini.google.com → Deep Think mode
  2. Copy-paste the contents of PROMPT.md as your message
  3. Upload files 00 through 08 (9 files)
  4. After receiving the response, paste it back and save as:
     diagnosis/deepthink/YYYY-MM-DD/round_N_reply.md
  5. To iterate: patch code locally, then re-invoke /deepthink-review
```

---

## ROUND CONTINUATION PROTOCOL

When the user pastes back a reply from Gemini Deep Think:

1. Save the raw reply to `diagnosis/deepthink/YYYY-MM-DD/round_N_reply.md`
2. **Generate meeting notes** (see MEETING NOTES section below)
3. Inform the user: "Saved Round N reply + meeting notes. Make your local changes, then run `/deepthink-review` to generate Round N+1."

When `/deepthink-review` is invoked and prior rounds exist:

1. Detect the latest round number
2. Read the prior reply file
3. Compute `git diff [old_sha]..HEAD`
4. Include both in the new PROMPT.md under "Previous Round Feedback" and "Changes Since Round N"
5. Re-consolidate the updated codebase into fresh files

---

## MEETING NOTES

When the user pastes back a model reply, generate a structured meeting note that distills the feedback into actionable form. This note serves as the record for subsequent brainstorming sessions.

### Output file
`diagnosis/deepthink/YYYY-MM-DD/round_N_meeting_notes.md`

### Template

```markdown
# Meeting Notes: Gemini Deep Think Code Review — Round [N]

**Date:** [YYYY-MM-DD]
**Reviewer:** Gemini Deep Think (Google)
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
_Generated by Claude from Gemini Deep Think feedback_
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

## MAXIMUM VERBOSITY PROTOCOL

**Always apply this protocol to every Gemini Deep Think prompt.** Gemini has a strong tendency to abbreviate — saying "remains unchanged" without proof, giving one-sentence proof sketches, or providing high-level descriptions instead of complete LaTeX. This is unacceptable for academic research.

### Mandatory Prompt Language

Every PROMPT.md must include the following directive block near the top of "Your Task":

```markdown
**CRITICAL INSTRUCTIONS ON VERBOSITY AND DETAIL:**

This is a rigorous academic research project. Your response must be **exhaustive, meticulous, and complete**. Specifically:

1. **Do NOT abbreviate.** Do not say "the rest is analogous" or "remains unchanged" without providing a complete algebraic proof showing WHY it is unchanged.
2. **Do NOT provide proof sketches.** Provide complete proofs with every algebraic step shown.
3. **Do NOT summarize.** If a proposition needs rewriting, provide the complete camera-ready LaTeX, not a description of what it should say.
4. **Show ALL algebra.** Every derivative, every substitution, every simplification step.
5. **Your response should be VERY LONG.** A short response means you have abbreviated something. We expect and want a long, detailed response.
6. **For code changes:** Provide complete function implementations, not skeletons with "..." or "setup unchanged."
7. **For LaTeX changes:** Provide the exact replacement text with line number boundaries, ready to paste into the manuscript.
8. **Verify your own work.** After providing a fix, trace through it step by step to confirm correctness.

The cost of verbosity is zero. The cost of a gap in a proof is a desk reject. Err on the side of too much detail, never too little.
```

### Mandatory Anti-Sycophancy Language

Gemini has a strong tendency toward sycophancy — opening with "brilliant analysis," "impeccably documented," or similar flattery before agreeing with everything the user said. This is actively harmful for academic work. Every PROMPT.md must include the following directive:

```markdown
**CRITICAL INSTRUCTIONS ON INTELLECTUAL HONESTY:**

I am a serious academic researcher. I need your **honest, independent judgment** — not agreement, not flattery, not validation.

1. **Do NOT open with compliments.** Skip "brilliant," "impressive," "well-documented." Go straight to substance.
2. **Do NOT agree with my analysis just because I presented it.** If my root cause diagnosis is wrong, say so. If my proposed fix has a flaw I haven't seen, tell me.
3. **Challenge my assumptions.** If I claim something "must be structural," but you see a parametric fix I missed, say so. If I ruled out an approach prematurely, push back.
4. **Flag where I might be wrong.** Even if you broadly agree, identify the weakest points in my reasoning and stress-test them.
5. **Distinguish your confidence levels.** Say "I am confident that X" vs "I suspect Y but haven't verified" vs "Z is speculative." Do not present uncertain claims with false confidence.
6. **Prioritize correctness over my feelings.** A polite "your proof is flawed at step 3" is infinitely more valuable than an enthusiastic "great work, here's how to extend it."

I would rather receive a harsh, correct assessment that saves me from a referee embarrassment than a warm, agreeable one that lets an error through. Treat me as a colleague submitting to a top-5 journal, not as a student seeking encouragement.
```

### When to Intensify Further

If a previous Gemini round was abbreviated (Claude flags this in meeting notes), the follow-up prompt must:

1. **Explicitly list every gap** from the previous round with line references
2. **Quote the abbreviated text** and say "This is NOT sufficient — provide [specific request]"
3. Add: "Your previous response was helpful but significantly abbreviated in the implementation details. This follow-up round requires your MOST EXHAUSTIVE pass. Do not leave any derivation incomplete."

---

## IMPORTANT NOTES

- **Never include `diagnosis/` in consolidated files** — recursive packaging
- **Never include `.claude/`** — Claude Code meta files are not part of the codebase
- **Never include raw data** (`data/` directory) — too large, not needed
- **Text only** — no binary files. Use `.tex` source for reports, `.R` code for figures
- **Always verify freshness before packaging** — stale outputs are the #1 contamination vector
- **Each round is a clean reconsolidation** — old rounds preserved but never mixed into new packages
- **Max ~10 files** — the 9 consolidated files + PROMPT.md = 10. If a project is very small, merge files to use fewer. If very large, consolidate more aggressively but never exceed 10.
