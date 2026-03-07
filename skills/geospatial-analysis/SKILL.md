---
name: geospatial-analysis
description: Use when working with maps, regions, spatial joins, geospatial files, or public statistical data tied to places.
---

# Geospatial Analysis

## Overview

Front door for location-aware analysis. This skill covers vector geospatial work, broader remote-sensing style workflows when needed, and public-statistics tasks where place is the organizing key.

## Use This For

- shapefiles, GeoJSON, GeoPackages
- spatial joins, overlays, buffers, and reprojection
- regional statistics tied to maps or geographies
- map-ready data preparation
- location-aware public-data workflows

## Do Not Use This For

- ordinary non-spatial charts: use `visualization`
- general tabular analysis with no geographic structure: use `empirical-analysis-python`

## Internal Routing

- GeoPandas-style vector workflows
- broader geospatial science workflows
- place-linked public data

## Operating Rule

If geography is part of the data model rather than just a label on the chart, start here.
