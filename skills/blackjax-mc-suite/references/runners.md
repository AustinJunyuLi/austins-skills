# Canonical Runners

## Source of truth
`README.md` is the canonical runbook.

## Narrow entrypoints

### Single fit

```bash
hmc-fit --spec N1 --N 100 --seed 42 --ppc
```

Use this first when debugging a model change, data issue, or diagnostic concern.

### Monte Carlo grid

```bash
hmc-mc --all-specs --Ns 50 100 200 --reps 10 --fp64 \
  --out-dir outputs/hmc/mc_parquet
```

Use isolated `--out-dir` values when comparing dropout settings or DGP mechanisms.

### Dropout grid post-processing

```bash
python3 scripts/combine_dropout_grid.py --overwrite
python3 scripts/analyze_mc_results.py outputs/hmc/mc_parquet_dropout_grid
hmc-figures outputs/hmc/mc_parquet_dropout_grid
```

## Canonical suite runners

### Baseline GPT Pro suite

```bash
bash scripts/run_gptpro_suite.sh
```

### Minimal DGP dropout suite

```bash
bash scripts/run_dgp_dropout_minimal_suite.sh
```

### Holistic suite

```bash
bash scripts/run_holistic_suite.sh
```

## Output discipline
- `hmc-mc` writes Parquet checkpoints plus `run_config.json` to `--out-dir`.
- Suite runners create tagged output roots under `outputs/` and bundle tarballs at the end.
- Keep one logical experiment per output root so resume behavior stays meaningful.
