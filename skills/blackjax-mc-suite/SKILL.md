---
name: blackjax-mc-suite
description: Use when the informal_bids repo task involves hmc-fit or hmc-mc runs, dropout suite orchestration, checkpointed Monte Carlo outputs, diagnostics triage, or figure-pack generation.
---

# BlackJAX MC Suite

## Overview
Use this skill for the repository's production estimation workflow: single fits, Monte Carlo grids, dropout suites, post-processing, figure generation, and packaged reportable outputs.

## When to Use
- Use when the task touches `hmc-fit`, `hmc-mc`, `hmc-figures`, suite runner scripts, or Monte Carlo post-processing.
- Use when the problem is checkpoint resume, diagnostics gating, dropout-grid organization, or figure-pack completion.
- Use when output directories, `run_config.json`, or tarball bundles matter to correctness.
- Do not use for workbook-to-canonical data work. Use `informal-bids-canonical-data`.
- Do not use for generic model editing without run orchestration concerns. Use `empirical-analysis-python` or `ml-systems`.

Read [`references/runners.md`](./references/runners.md) first for canonical commands and output layout.
Read [`references/diagnostics.md`](./references/diagnostics.md) when runs fail, resume, or produce incomplete artifacts.

## Core Procedure
1. Pick the narrowest entrypoint: single fit, MC grid, or full suite.
2. Preserve output-dir discipline so checkpoints and `run_config.json` remain interpretable.
3. Preflight plotting and runtime dependencies before expensive runs.
4. Reuse checkpointed outputs where possible; do not mix incompatible settings into one out-dir.
5. Verify diagnostics and figures before packaging or reporting results.

## Common Mistakes
- Running a large suite before checking `Rscript` and plotting packages.
- Mixing multiple dropout settings into the same output directory.
- Treating missing figures as model failure when post-processing failed.
- Ignoring `run_config.json` and resuming a run with mismatched assumptions.
- Using legacy MH outputs as if they were the production baseline.
