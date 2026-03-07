---
name: citation-management
description: Use when a paper, slide deck, or literature review needs citation search, DOI or PMID metadata lookup, BibTeX cleanup, or bibliography validation.
---

# Citation Management

## Overview

Use the bundled scripts for citation lookup, metadata extraction, BibTeX cleanup, and validation. Keep the workflow mechanical and script-first; use `research-discovery` for narrative literature synthesis.

## When to Use

- Searching Google Scholar or PubMed for papers
- Converting DOI, PMID, arXiv ID, or URL metadata into BibTeX
- Cleaning or deduplicating a `.bib` file
- Checking a bibliography before submission
- Fixing inconsistent or missing citation metadata

Do not use this skill for general writing or thematic synthesis alone.

## Fast Paths

Single DOI to BibTeX:

```bash
python3 {{SKILLS_ROOT}}/citation-management/scripts/doi_to_bibtex.py \
  10.1038/s41586-021-03819-2
```

Identifier or URL to metadata:

```bash
python3 {{SKILLS_ROOT}}/citation-management/scripts/extract_metadata.py \
  --doi 10.1038/s41586-021-03819-2 \
  --output references.bib
```

PubMed search:

```bash
python3 {{SKILLS_ROOT}}/citation-management/scripts/search_pubmed.py \
  "auction screening" \
  --limit 50 \
  --output pubmed_results.json
```

Google Scholar search:

```bash
python3 {{SKILLS_ROOT}}/citation-management/scripts/search_google_scholar.py \
  "blockholder disclosure" \
  --limit 50 \
  --output scholar_results.json
```

Format and deduplicate:

```bash
python3 {{SKILLS_ROOT}}/citation-management/scripts/format_bibtex.py \
  references.bib \
  --deduplicate \
  --sort year
```

Validate a bibliography:

```bash
python3 {{SKILLS_ROOT}}/citation-management/scripts/validate_citations.py \
  references.bib \
  --report validation.json
```

## Recommended Workflow

1. Search for papers or gather identifiers.
2. Extract metadata into a working `.bib` file.
3. Format and deduplicate the bibliography.
4. Validate it and spot-check the highest-value entries manually.
5. Only then wire the references into LaTeX, Quarto, or slides.

If script flags are unclear, use `--help` on the relevant script.

## References

Read only what you need:

- `references/google_scholar_search.md` for Scholar search tactics
- `references/pubmed_search.md` for PubMed syntax and API details
- `references/metadata_extraction.md` for identifier handling
- `references/citation_validation.md` for validation rules
- `references/bibtex_formatting.md` for BibTeX conventions

## Common Mistakes

- Typing BibTeX entries by hand instead of extracting metadata
- Leaving duplicate entries after merging bibliographies
- Citing a preprint when a published version exists
- Skipping validation before submission
- Treating automated metadata as correct without spot-checking key papers
