# Shared Invariants

## Data and Time

- Use minute OHLCV inputs as the source of truth.
- Keep exchange-time logic explicit.
- Treat the CME maintenance hour as a QC signal, not normal trading activity.

## Curve and Roll Logic

- Check whether the repo wants expiry-ranked strips, volume-crossover rolls, or both.
- Preserve the repo's distinction between:
  - tradable held returns for PnL
  - adjusted prices for signals or analytics
- Avoid silent forward fills across contract gaps or roll boundaries.

## Research Integrity

- Backtests must lag weights and signals correctly.
- Walk-forward folds must not leak future data into training windows.
- Use targeted tests around data, rolls, and walk-forward code before running long jobs.

## Useful Entry Points

- `future_project_1`: `python3 -m futures_curve.cli run --config config/default.yaml`
- `future_project_1`: `pytest -q`
- `rf`: inspect `scripts/run_pipeline.py` and `tests/test_pipeline.py`
- `rl_trade`: inspect `tests/test_walkforward.py`, `tests/test_evaluation.py`, and `tests/test_data.py`
