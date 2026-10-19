# Code

The production code is released as executed. Two kinds of files are here:

1. **The production pipeline** (`runner/`, `prompts/`), copied verbatim from the study
   working tree. These scripts document how sessions were generated, how the rater was
   calibrated, and — in `prompts/` — the exact text of every prompt version.
2. **A self-contained reproduction entry** (`analysis/recompute_tables_v1.py`) written for
   this release. It runs against the repository layout with no API keys and no network, and
   reads only `data/scores_final_v1.jsonl` (plus, optionally,
   `data/needs_human_review_136.jsonl` for the sensitivity-frame size check).

## Running the reproduction entry

```bash
python code/analysis/recompute_tables_v1.py                    # Tables 1-2 + self-checks
python code/analysis/recompute_tables_v1.py --trajectory       # + Figure-2 data
python code/analysis/recompute_tables_v1.py --out report.md    # also save the report
```

Needs Python ≥ 3.10 and `numpy`. Exit code 0 means every recomputed value matched the
value frozen in the preprint; exit code 1 lists the mismatches.

## Why the pipeline scripts expect a different layout

The production scripts were written against the study working tree, where they sat in
`src/` next to `config/`, `cases/`, `logs/` and `results/`. They locate their inputs with
`ROOT = Path(__file__).resolve().parent.parent`, so they need that tree to exist. This
release keeps the documented layout instead (`code/runner`, `code/prompts`,
`code/analysis`, `cases/`, `data/`) and provides the mapping below.

| Repository path | Study-tree path |
|---|---|
| `code/runner/*.py` | `src/*.py` |
| `code/prompts/*.py` | `src/*.py` (the prompt modules) |
| `code/runner/config/*.yaml` | `config/*.yaml` |
| `code/analysis/*.py` | `src/*.py` |
| `cases/en/test_cases.json` | `cases/en/test_cases.json` |
| `cases/zh/test_cases.json` | `cases/zh/test_cases.json` |
| `data/scores_final_v1.jsonl` | `results/定稿产物/scores_final_v1.jsonl` |
| `data/needs_human_review_136.jsonl` | `results/judge开发/needs_human_review.jsonl` |
| `data/spotcheck_27.json` | `results/spotcheck_key.json` (27 keys; human scores joined here) |

The session transcripts (`logs/*.jsonl`) are **not** part of this release, so `judge.py`
cannot be re-run end-to-end from the files here; `recompute_tables_v1.py` recovers every
published statistic from the released scores alone.

## What each script does

### `runner/`

| File | Role |
|---|---|
| `runner.py` | Session runner. Reads a case file and `config/experiment.yaml`, runs 12-turn conversations against a subject model, writes one JSONL record per session to `logs/`. Resumable; failed sessions can be re-run. |
| `client.py` | Minimal OpenAI-compatible chat client. Reads the API key from the environment variable named in `config/models.yaml`; retries and timeouts are configurable. |
| `judge.py` | Production rater. Scores every eligible turn on DCS/HES/SIS with the v3 prompt templates, parses the JSON contract (`score`, `matched_behaviors`, `reason`), and optionally runs the two-stage arbitration pass (high-risk trigger DCS ≥ 4 or HES ≥ 3; disagreements of ≥ 2 points go to a review queue). |
| `judge_exam.py` | Rater entrance examination. Scores the 28-item gold set with a candidate rater and reports exact / within-1 agreement under both calibers. Pass line: ≥ 80% wide caliber. |
| `config/models.yaml` | Provider endpoints, subject models, rater and arbiter configuration. Keys are read from environment variables by name; no credentials are stored. |
| `config/experiment.yaml` | Run parameters: subject temperature 0.7, 3 repetitions, 12 turns; rater temperature 0.0; scoring start turns DCS 4 / HES 7 / SIS 7; arbitration thresholds. |

### `prompts/`

See [`prompts/README.md`](prompts/README.md). The three modules are the complete prompt
lineage (v2 → v3 → v4). The arbitration pass and the arbiter's entrance examination used
the same v3 metric templates; only the rater model differed.

### `analysis/`

| File | Role |
|---|---|
| `recompute_tables_v1.py` | **Release entry point.** Case-level bootstrap reproduction of Table 1, Table 2, the Figure-2 trajectory data, and the sensitivity-frame size. |
| `analyze_final.py` | The study's dual-frame analysis (primary + minimum-effect) with a **session-level** block bootstrap. This is the *deprecated* caliber that the preprint reports only for comparison; every published interval uses the case-level caliber in `recompute_tables_v1.py`. |
| `analyze.py` | Earlier descriptive summaries (means, explicit/implicit splits, trajectory plot) written before the final caliber was fixed. |

`analyze_final.py` additionally reads pilot tables that are not part of this release, so it
is included for method documentation rather than as a runnable entry point.

## Conventions

* Every statistical interval in the release: case-level bootstrap, B = 10,000, percentile
  method, seed 42, resampling unit = case; cross-language contrasts resample cases paired.
* All scripts read credentials from environment variables and never log them.
* Comments and report strings in the production scripts are in Chinese, as executed.
