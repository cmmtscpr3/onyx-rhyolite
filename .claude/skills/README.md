# Claude Skills: Data Analytics

Six Claude Code skills covering the data analytics workflow, from warehouse
modeling through analysis, experimentation, and production ML.

Claude loads these automatically when a task matches a skill's description —
no configuration needed. You can also invoke one by name.

## Catalog

| Skill | Use it for |
|-------|-----------|
| `data-analyst` | SQL queries, cohort and funnel analysis, visualization, business reporting |
| `statistical-analyst` | Test selection, assumption checks, power planning, effect sizes, multiplicity correction |
| `data-scientist` | Feature engineering, ML algorithm selection, A/B test design, model evaluation |
| `business-intelligence` | Dashboard design, KPI frameworks, report automation, data storytelling |
| `analytics-engineer` | dbt models, star schemas, staging/mart SQL, data tests, warehouse optimization |
| `ml-ops-engineer` | Model deployment, training pipelines, drift detection, feature stores, ML CI/CD |

### Choosing between overlapping skills

- **`data-analyst` vs `business-intelligence`** — exploratory, one-off analysis
  goes to `data-analyst`; repeatable dashboards and KPI systems go to
  `business-intelligence`.
- **`data-scientist` vs `statistical-analyst`** — predictive modeling and
  feature work goes to `data-scientist`; interpreting an experiment, sizing a
  study, or vetting a statistical claim goes to `statistical-analyst`.
- **`data-scientist` vs `ml-ops-engineer`** — model development and
  experimentation goes to `data-scientist`; production deployment and
  monitoring goes to `ml-ops-engineer`.
- **`analytics-engineer`** builds the reliable data models the other skills
  depend on.

## Layout

Each skill directory follows the standard structure:

- `SKILL.md` — the knowledge base Claude reads (required)
- `scripts/` — executable Python helpers
- `references/` — deeper documentation loaded on demand
- `assets/` — templates and sample input files

## Scripts

All 20 helper scripts use the Python standard library only — no pandas, no
numpy, nothing to install. Each has an `argparse` CLI with `--help`, and all
process files locally with no network access.

Machine-readable output is available from every script except
`analytics-engineer/scripts/doc_generator.py`, which emits markdown by design.
The flag differs by script: the four `statistical-analyst` scripts take
`--format json`, every other script takes a bare `--json`. (Separately,
`data-analyst/scripts/report_generator.py` has `--format {text,markdown}` to
pick its human-readable layout.) Check `--help` when in doubt.

```bash
# Run a two-proportion test with effect size and confidence interval
python3 .claude/skills/statistical-analyst/scripts/run_test.py \
  --input .claude/skills/statistical-analyst/assets/sample_experiment.json

# Profile a dataset's columns
python3 .claude/skills/data-analyst/scripts/data_profiler.py --help
```

The `statistical-analyst/assets/sample_*.json` files are runnable examples
that double as input-format documentation.

## Provenance

Vendored from [borghei/Claude-Skills](https://github.com/borghei/Claude-Skills),
directory [`data-analytics`](https://github.com/borghei/Claude-Skills/tree/main/data-analytics).

Licensed **MIT + Commons Clause** by Amin Borghei (borghei). Full terms in
[`LICENSE`](./LICENSE); the Commons Clause restricts selling the software.
Skill content is unmodified from upstream — update by re-copying from the
source repository rather than editing in place.
