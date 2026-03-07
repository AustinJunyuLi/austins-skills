---
name: finance-data
description: Use when pulling, cleaning, or organizing macro, Treasury, SEC, hedge fund, or market data for economics or finance work.
---

# Finance Data

## Overview

Front door for finance and macro data access. This skill groups public macro series, Treasury fiscal data, SEC filings, OFR hedge fund data, and market data into one coherent surface.

## Use This For

- FRED macro series
- U.S. Treasury Fiscal Data
- SEC EDGAR filings and XBRL financials
- OFR Hedge Fund Monitor data
- Alpha Vantage market data
- joining multiple public finance datasets into one pipeline

## Do Not Use This For

- estimating models or running diagnostics: use `empirical-analysis-python` or `data-analysis-r`
- forecasting or temporal model comparison: use `time-series-analysis`
- literature or policy background search: use `research-discovery`

## Internal Routing

- macro/public data
- fiscal and debt data
- filings and firm disclosures
- hedge fund/systemic risk data
- market and technical-indicator data

## Operating Rule

When the bottleneck is obtaining finance-relevant data rather than analyzing it, start here.
