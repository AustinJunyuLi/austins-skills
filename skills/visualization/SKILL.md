---
name: visualization
description: Use when the primary output is a figure, chart, network plot, or publication-ready visual analysis generated from data.
---

# Visualization

## Overview

Front door for data figures. This skill covers static, interactive, statistical, and network visualizations that are grounded in data rather than AI-generated artwork.

## Use This For

- journal figures
- exploratory charts
- interactive plots
- statistical graphics
- network visualizations
- multi-panel publication figures

## Do Not Use This For

- schematics, diagrams, or generated visual assets: use `research-graphics`
- map-heavy spatial workflows: use `geospatial-analysis`
- slide creation: use `slides-and-teaching`

## Internal Routing

- matplotlib for full control
- seaborn for statistical defaults
- plotly for interactive outputs
- networkx when graph structure is central

## Operating Rule

If the user’s core request is “make the figure,” start here.
