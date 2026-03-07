# Diagnostics And Verification

## Fast checks before expensive reruns
- Verify the Python environment and CLI entrypoints first.
- For suite scripts, confirm `Rscript` and required packages are available before long MC runs.
- Prefer a single `hmc-fit` or a small `hmc-mc` run before launching a full suite.

## Targeted verification commands

```bash
pytest tests/test_sampler.py tests/test_diagnostics.py -v
pytest tests/test_combine_dropout_grid.py tests/test_figures_export_latest.py -v
pytest tests/test_blackjax_layout.py tests/test_blackjax_likelihood.py -v
```

Use the narrowest subset that matches the code you touched.

## Resume and diagnostics rules
- Re-running the same `hmc-mc` command resumes from existing checkpoints in the target out-dir.
- Keep one dropout delta or one suite module per out-dir when the configuration changes materially.
- Use stronger diagnostics profiles or two-pass reruns only after confirming the failure is not a path or dependency issue.

## When figures are missing
- Check whether post-processing ran after MC completion.
- Re-run `python3 scripts/analyze_mc_results.py ...` and `hmc-figures ...` before assuming the estimator failed.
- For suite scripts, inspect the tagged `runlogs_*` directory and `STATUS.txt` under the output root.

## Production vs legacy
- `engine/blackjax/` is the production estimator path.
- `robustness/mh/` is validation-only and should not become the default run target.
