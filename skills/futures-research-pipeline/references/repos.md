# Repo Map

## `future_project_1`

- Purpose: canonical deterministic F1..F12 curve build plus DTE and BTE research.
- Start here for curve construction, spread panels, timezone inference, and report-table generation.
- Key files:
  - `future_project_1/README.md`
  - `future_project_1/src/futures_curve/cli.py`
  - `future_project_1/tests/test_stage1_ingestion.py`
  - `future_project_1/tests/test_stage2.py`

## `rf`

- Purpose: minimal factor pipeline for commodity futures using trend and carry.
- Start here for daily bars, continuous series, risk budgeting, and vectorized backtests.
- Key files:
  - `rf/docs/plans/2026-02-26-commodity-trading-design.md`
  - `rf/src/rf/pipeline.py`
  - `rf/scripts/run_pipeline.py`

## `rl_trade`

- Purpose: RL and stat-arb pipelines on commodity futures with walk-forward evaluation.
- Start here for spread discovery, reward logic, agent behavior, and evaluation metrics.
- Key files:
  - `rl_trade/README.md`
  - `rl_trade/tests/test_walkforward.py`
  - `rl_trade/tests/test_data.py`

## `futures_individual_contracts_1min`

- Purpose: older roll-analysis framework and legacy reference implementation.
- Use when the newer repos do not explain a calendar, roll, or CLI pattern clearly enough.
- Key files:
  - `futures_individual_contracts_1min/Archive/README.md`
