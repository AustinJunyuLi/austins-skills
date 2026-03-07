---
name: time-series-analysis
description: Use when the main problem is time-indexed data, forecasting, temporal features, sequence models, or forecast evaluation.
---

# Time Series Analysis

## Overview

Front door for sequence-first work. This skill handles forecasting, temporal feature design, time-series model comparison, and sequence-specific diagnostics.

## Use This For

- univariate or multivariate forecasting
- zero-shot forecasting with TimesFM
- aeon-based temporal modeling
- time-series feature engineering
- rolling evaluation, backtesting, and forecast comparison
- temporal anomaly detection or segmentation

## Do Not Use This For

- general tabular inference: use `empirical-analysis-python`
- deep learning systems not driven by a time-series problem statement: use `ml-systems`
- raw finance data retrieval: use `finance-data`

## Internal Routing

- fast classical baselines
- aeon workflows
- foundation-model forecasting
- evaluation and diagnostics

## Operating Rule

If the time axis is the core modeling object, this is the front door.
