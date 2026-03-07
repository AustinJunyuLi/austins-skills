---
name: compile-latex
description: Use when a LaTeX manuscript or Beamer deck needs compilation, citation resolution, and log triage.
---

# Compile LaTeX

## Overview
Use this skill when the task is to build a LaTeX artifact and verify that the output is current. Prefer the smallest compilation command that matches the repo's existing build flow, then inspect logs for broken citations, unresolved references, and overflow.

## When to Use
- Use when a `.tex` file or its generated PDF needs to be rebuilt.
- Use when bibliography changes require another compile pass.
- Use when the main risk is stale PDFs, undefined references, or LaTeX log warnings.
- Do not use for slide-content design or manuscript writing itself.

## Core Procedure
1. Inspect the repo's existing build entrypoint first: `latexmk`, `Makefile`, or a project-specific compile command.
2. Run the narrowest build that targets the changed file.
3. If the document has citations, ensure the build path resolves the bibliography.
4. Check the log for undefined citations, unresolved references, and overfull boxes.
5. Confirm the expected PDF was updated before declaring success.

## Build Patterns

### Preferred: existing repo command

Use the project's own command if it exists, for example:
- `latexmk -xelatex -interaction=nonstopmode file.tex`
- `make`
- a repo-specific `latexmk` or `xelatex` sequence

### Fallback: direct compile

```bash
xelatex -interaction=nonstopmode file.tex
bibtex file
xelatex -interaction=nonstopmode file.tex
xelatex -interaction=nonstopmode file.tex
```

Use this only when the repo does not already provide a safer build wrapper.

## Log Triage
- `undefined citations` or `Citation ... undefined`: bibliography problem
- `Label(s) may have changed`: rerun until cross-references stabilize
- `Overfull \hbox`: layout overflow to inspect
- missing included files or figures: path or generated-artifact problem

## Common Mistakes
- Compiling the PDF without checking whether the repo already uses `latexmk` or `make`.
- Declaring success after a build that still has unresolved citations.
- Treating an old PDF as current without checking timestamps or rerunning the target build.
- Fixing visual overflow only in the PDF instead of tracing it back to the source.
