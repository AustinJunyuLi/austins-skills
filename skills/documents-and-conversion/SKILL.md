---
name: documents-and-conversion
description: Use when the main job is reading, extracting, converting, repairing, or restructuring PDF, DOCX, PPTX, XLSX, or related document files.
---

# Documents And Conversion

## Overview

Front door for file surgery and file conversion. This skill handles documents as files first: extraction, cleanup, conversion, merge/split, OCR, and reformatting.

## Use This For

- converting files to markdown
- extracting text, tables, or images
- fixing broken spreadsheets or slide files
- combining or splitting PDFs
- normalizing DOCX, PPTX, or XLSX content
- file-level transformations across formats

## Do Not Use This For

- writing a paper or grant: use `research-writing`
- building a talk or lecture deck: use `slides-and-teaching`
- analyzing the data inside the file as the main goal: use `empirical-analysis-python` or `data-analysis-r`

## Internal Routing

- PDF operations
- Word and PowerPoint manipulation
- spreadsheet file cleanup
- broad format conversion through markdown

## Operating Rule

If the user’s bottleneck is the file format itself, start here.
