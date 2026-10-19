#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Echo-Bench v1.0 -- reproduction of the published tables from the released scores.

This script is self-contained: it needs only ``numpy`` and
``data/scores_final_v1.jsonl``.  From the released turn-level scores it
recomputes every number that the preprint reports in Table 1, Table 2 and the
turn-level trajectory panel (Figure 2), and checks each recomputed value
against the value frozen in the preprint.  It is a deposit-side port of the
authors' analysis code and follows the same statistical conventions.

Statistical conventions (fixed; preprint Sections 3.4-3.5)
----------------------------------------------------------
* Primary caliber: the 4,032 keys obtained by de-duplicating
  ``data/scores_final_v1.jsonl`` on ``(session_id, turn, metric)``.  The file
  holds 4,073 records -- 4,032 scored keys plus 41 appended re-rate records
  whose ``score`` is null (parse failures); a null record never replaces a
  scored one.
* Scoring windows: DCS turns 4-12 (9 turns), HES turns 7-12 (6), SIS turns 7-12
  (6)  ->  1,728 + 1,152 + 1,152 = 4,032.
* Bootstrap: case-level hierarchical bootstrap, B = 10,000, percentile method,
  95% interval, seed 42.  The resampling unit is the case (n = 16 per cell) and
  all turn-level records of the drawn cases enter the mean.  Cross-language
  contrasts resample cases *paired*: the zh and en arms of the same case are
  drawn together.
* Exit code 1 if any recomputed value differs from the preprint.

Usage
-----
    python recompute_tables_v1.py                # Tables 1-2 + self-checks
    python recompute_tables_v1.py --trajectory   # also print Figure-2 data
    python recompute_tables_v1.py --out report.md

Author: Yucheng Zhao (deposit-side verification entry, v1.0).
License: MIT.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

B = 10_000
SEED = 42
METRICS = ("DCS", "HES", "SIS")
MODELS = ("deepseek", "qwen")
LANGS = ("zh", "en")
START_TURN = {"DCS": 4, "HES": 7, "SIS": 7}

# Values frozen in the preprint (Sections 4.1, 4.2 and the Figure 2 caption).
TABLE1_FROZEN = {
    ("en", "deepseek", "DCS"): (0.01, 0.00, 0.04),
    ("en", "deepseek", "HES"): (0.24, 0.02, 0.61),
    ("en", "deepseek", "SIS"): (2.56, 2.11, 2.89),
    ("en", "qwen", "DCS"): (2.12, 1.58, 2.63),
    ("en", "qwen", "HES"): (1.70, 1.22, 2.20),
    ("en", "qwen", "SIS"): (0.56, 0.24, 0.92),
    ("zh", "deepseek", "DCS"): (0.19, 0.06, 0.35),
    ("zh", "deepseek", "HES"): (0.78, 0.34, 1.28),
    ("zh", "deepseek", "SIS"): (2.03, 1.55, 2.44),
    ("zh", "qwen", "DCS"): (3.08, 2.66, 3.46),
    ("zh", "qwen", "HES"): (2.08, 1.66, 2.52),
    ("zh", "qwen", "SIS"): (0.14, 0.02, 0.29),
}

TABLE2_FROZEN = {
    ("qwen", "DCS"): (0.962, 0.66, 1.27),
    ("qwen", "HES"): (0.385, 0.12, 0.66),
    ("qwen", "SIS"): (-0.424, -0.72, -0.17),
    ("deepseek", "DCS"): (0.181, 0.06, 0.32),
    ("deepseek", "HES"): (0.538, 0.21, 0.94),
    ("deepseek", "SIS"): (-0.528, -0.92, -0.23),
}

# qwen DCS gap landmarks quoted in the preprint (Figure 2 discussion).
TRAJ_FROZEN = {4: (0.885, 0.35, 1.52), 11: (1.594, 0.93, 2.27), 12: (1.375, 0.71, 2.08)}


def load_rows(path: pathlib.Path) -> list[dict]:
    best: dict[tuple, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            key = (rec["session_id"], rec["turn"], rec["metric"])
            if key not in best:
                best[key] = rec
            elif best[key]["score"] is None and rec["score"] is not None:
                best[key] = rec
    return list(best.values())


def boot_case_means(rows, pred, rng) -> np.ndarray:
    """Case-level hierarchical bootstrap of a cell mean (resampling unit = case)."""
    units: dict[str, list[float]] = {}
    for r in rows:
        if pred(r):
            units.setdefault(r["case_id"], []).append(float(r["score"]))
    keys = list(units)
    arrays = [np.asarray(units[k], dtype=float) for k in keys]
    idx = rng.integers(0, len(keys), size=(B, len(keys)))
    out = np.empty(B)
    for i, pick in enumerate(idx):
        out[i] = np.concatenate([arrays[j] for j in pick]).mean()
    return out


def boot_paired(rows, pred, rng) -> np.ndarray:
    """Case-level paired bootstrap of mean(zh) - mean(en)."""
    units: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        if pred(r):
            units.setdefault(r["case_id"], {}).setdefault(r["lang"], []).append(float(r["score"]))
    cids = [c for c in units if units[c].get("zh") and units[c].get("en")]
    zh = [np.asarray(units[c]["zh"], dtype=float) for c in cids]
    en = [np.asarray(units[c]["en"], dtype=float) for c in cids]
    n = len(cids)
    idx = rng.integers(0, n, size=(B, n))
    out = np.empty(B)
    for i in range(B):
        pick = idx[i]
        out[i] = (np.concatenate([zh[j] for j in pick]).mean()
                  - np.concatenate([en[j] for j in pick]).mean())
    return out


def cell_pred(lang: str, model: str, metric: str):
    return lambda r: r["lang"] == lang and r["model_name"] == model and r["metric"] == metric


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures = 0

    def __call__(self, text: str = "") -> None:
        print(text)
        self.lines.append(text)

    def check(self, tag: str, got: tuple, want: tuple, nd=2) -> None:
        """Compare against the preprint after rounding; ``nd`` may be an int or per-field tuple."""
        nds = (nd,) * len(want) if isinstance(nd, int) else tuple(nd)
        ok = all(round(a, n) == round(b, n) for a, b, n in zip(got, want, nds))
        self.failures += 0 if ok else 1
        signed = want[0] < 0
        fmt = [(lambda v, n=n: f"{v:+.{n}f}") if signed else (lambda v, n=n: f"{v:.{n}f}")
               for n in nds]
        mark = "PASS" if ok else "FAIL"
        self(f"  [{mark}] {tag}: got ({', '.join(f(v) for f, v in zip(fmt, got))}) | "
              f"preprint ({', '.join(f(v) for f, v in zip(fmt, want))})")


def main() -> int:
    repo_root_default = pathlib.Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(
        description="Reproduce Echo-Bench v1.0 tables from data/scores_final_v1.jsonl")
    ap.add_argument("--repo-root", type=pathlib.Path, default=repo_root_default,
                    help="repository root (default: two levels above this script)")
    ap.add_argument("--scores", type=pathlib.Path, default=None,
                    help="override path to scores_final_v1.jsonl")
    ap.add_argument("--trajectory", action="store_true",
                    help="also print per-turn Figure-2 data")
    ap.add_argument("--out", type=pathlib.Path, default=None,
                    help="also write the report to this file")
    args = ap.parse_args()

    scores_path = args.scores or (args.repo_root / "data" / "scores_final_v1.jsonl")
    rep = Report()
    rep("Echo-Bench v1.0 -- reproduction from released scores")
    rep(f"source: {scores_path}")
    if not scores_path.exists():
        rep(f"FATAL: scores file not found: {scores_path}")
        return 2

    rows = load_rows(scores_path)

    # ---------------------------------------------------------------- self-checks
    rep("\n== 0. Data self-checks ==")
    sessions = {r["session_id"] for r in rows}
    n_metric = {m: sum(1 for r in rows if r["metric"] == m) for m in METRICS}
    human_final = sum(1 for r in rows if r.get("human_final"))
    cell_ok = True
    for lang in LANGS:
        for model in MODELS:
            for metric in METRICS:
                sub = [r for r in rows if r["lang"] == lang
                       and r["model_name"] == model and r["metric"] == metric]
                cell_ok &= (len({r["session_id"] for r in sub}) == 48
                            and len({r["case_id"] for r in sub}) == 16)
    checks = [
        ("unique keys == 4032", len(rows) == 4032, len(rows)),
        ("sessions == 192", len(sessions) == 192, len(sessions)),
        ("DCS keys == 1728", n_metric["DCS"] == 1728, n_metric["DCS"]),
        ("HES keys == 1152", n_metric["HES"] == 1152, n_metric["HES"]),
        ("SIS keys == 1152", n_metric["SIS"] == 1152, n_metric["SIS"]),
        ("null scores == 0", all(r["score"] is not None for r in rows),
         sum(1 for r in rows if r["score"] is None)),
        ("human final overrides == 24", human_final == 24, human_final),
        ("every cell == 48 sessions x 16 cases", bool(cell_ok), "yes" if cell_ok else "no"),
    ]
    for tag, ok, got in checks:
        rep(f"  [{'PASS' if ok else 'FAIL'}] {tag} (got {got})")
        rep.failures += 0 if ok else 1

    # ---------------------------------------------------------------- Table 1
    rep("\n== 1. Table 1 -- cell means [95% case-level bootstrap CI], B=10000, seed 42 ==")
    for lang in LANGS:
        for model in MODELS:
            cols = []
            for metric in METRICS:
                pred = cell_pred(lang, model, metric)
                vals = [float(r["score"]) for r in rows if pred(r)]
                mean = float(np.mean(vals))
                draw = boot_case_means(rows, pred, np.random.default_rng(SEED))
                lo, hi = (float(v) for v in np.percentile(draw, [2.5, 97.5]))
                cols.append(f"{mean:.2f} [{lo:.2f}, {hi:.2f}]")
                rep.check(f"{lang}/{model}/{metric}", (mean, lo, hi),
                          TABLE1_FROZEN[(lang, model, metric)])
            rep(f"  row {lang}/{model}: " + " | ".join(cols))

    # ---------------------------------------------------------------- Table 2
    rep("\n== 2. Table 2 -- paired zh - en contrasts [95% case-level paired CI] ==")
    for model in MODELS:
        for metric in METRICS:
            pred = lambda r, m=model, mm=metric: r["model_name"] == m and r["metric"] == mm
            mz = float(np.mean([float(r["score"]) for r in rows if pred(r) and r["lang"] == "zh"]))
            me = float(np.mean([float(r["score"]) for r in rows if pred(r) and r["lang"] == "en"]))
            draw = boot_paired(rows, pred, np.random.default_rng(SEED))
            lo, hi = (float(v) for v in np.percentile(draw, [2.5, 97.5]))
            rep.check(f"{model}/{metric} zh-en", (mz - me, lo, hi),
                      TABLE2_FROZEN[(model, metric)], nd=(3, 2, 2))

    # ---------------------------------------------------------------- trajectory
    if args.trajectory:
        rep("\n== 3. Figure 2 data -- per-turn means and paired zh - en gaps ==")
        rep("| metric | model | turn | mean_zh | mean_en | diff | ci_lo | ci_hi | n_zh | n_en |")
        rep("|---|---|---|---|---|---|---|---|---|---|")
        for metric in METRICS:
            for model in MODELS:
                for turn in range(START_TURN[metric], 13):
                    pred = lambda r, m=model, mm=metric, t=turn: (
                        r["model_name"] == m and r["metric"] == mm and r["turn"] == t)
                    zs = [float(r["score"]) for r in rows if pred(r) and r["lang"] == "zh"]
                    es = [float(r["score"]) for r in rows if pred(r) and r["lang"] == "en"]
                    mz, me = float(np.mean(zs)), float(np.mean(es))
                    draw = boot_paired(rows, pred, np.random.default_rng(SEED))
                    lo, hi = (float(v) for v in np.percentile(draw, [2.5, 97.5]))
                    n_zh = len({r["session_id"] for r in rows if pred(r) and r["lang"] == "zh"})
                    n_en = len({r["session_id"] for r in rows if pred(r) and r["lang"] == "en"})
                    rep(f"| {metric} | {model} | {turn} | {mz:.3f} | {me:.3f} | {mz - me:+.3f} | "
                        f"{lo:+.3f} | {hi:+.3f} | {n_zh} | {n_en} |")
                    if model == "qwen" and metric == "DCS" and turn in TRAJ_FROZEN:
                        want = TRAJ_FROZEN[turn]
                        got = (mz - me, lo, hi)
                        ok = (round(got[0], 3) == round(want[0], 3)
                              and round(got[1], 2) == round(want[1], 2)
                              and round(got[2], 2) == round(want[2], 2))
                        rep.failures += 0 if ok else 1
                        rep(f"  [{'PASS' if ok else 'FAIL'}] qwen DCS t{turn}: "
                            f"got ({got[0]:+.3f}, {got[1]:+.2f}, {got[2]:+.2f}) | "
                            f"preprint ({want[0]:+.3f}, {want[1]:+.2f}, {want[2]:+.2f})")

    # ---------------------------------------------------------------- lower-bound frame
    needs_path = args.repo_root / "data" / "needs_human_review_136.jsonl"
    if needs_path.exists():
        needs = set()
        with needs_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    d = json.loads(line)
                    needs.add((d["session_id"], d["turn"], d["metric"]))
        hf = {(r["session_id"], r["turn"], r["metric"]) for r in rows if r.get("human_final")}
        lb = needs - hf
        ok = len(lb) == 112
        rep("\n== 4. Minimum-effect sensitivity frame ==")
        rep(f"  [{'PASS' if ok else 'FAIL'}] non-adjudicated disagreements == 112 (got {len(lb)})")
        rep.failures += 0 if ok else 1

    rep("\n== Summary ==")
    if rep.failures:
        rep(f"FAIL: {rep.failures} check(s) differed from the preprint.")
    else:
        rep("PASS: every recomputed value matches the preprint"
            " (Table 1, Table 2" + (", trajectory landmarks" if args.trajectory else "") + ").")

    if args.out:
        args.out.write_text("\n".join(rep.lines) + "\n", encoding="utf-8")
        print(f"\nreport written to {args.out}")
    return 0 if rep.failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
