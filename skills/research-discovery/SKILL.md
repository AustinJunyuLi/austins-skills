---
name: research-discovery
description: Use when finding papers, current sources, citations, or research materials for a topic, claim, literature sweep, or background memo.
---

# Research Discovery

## Overview

Front door for finding and organizing research sources. This skill absorbs literature search, current-information lookup, citation discovery, and research-material ingestion.

## Use This For

- finding papers on a topic
- checking what is recent or current
- building a literature sweep
- verifying citations or source metadata
- combining academic databases with web-grounded search
- collecting materials into a notebook-style workspace

## Do Not Use This For

- generating hypotheses or research directions: use `research-ideation`
- drafting prose or a manuscript: use `research-writing`
- evaluating a finished paper or grant: use `research-review`

## Internal Routing

- Academic search: OpenAlex, PubMed, bioRxiv, BGPT
- Current-information search: Perplexity, Parallel
- Citation cleanup: citation-management workflows
- Material ingestion: notebook-style source organization

## Operating Rule

Start broad, then narrow. First identify the source class you need, then choose the backend inside this skill. Do not open multiple sibling skills for the same search intent.
