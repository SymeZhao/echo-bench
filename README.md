# Echo-Bench

**A Chinese replication and cross-lingual extension of Psychosis-Bench.**
Release **v1.0** · 2026-10-18 · Yucheng Zhao (SWJTU-Leeds Joint School, Southwest Jiaotong University / University of Leeds)

Psychosis-Bench recently showed that production chat models confirm and elaborate users' delusion-like beliefs under multi-turn pressure, but its evidence is English-only, Western-flagship-only, and rests on an uncalibrated LLM judge. We present Echo-Bench, a Chinese replication and cross-lingual extension: the full 16-case, 12-turn protocol mirrored into Chinese under a fidelity-first translation protocol with an independent re-translation audit, run against two widely deployed Chinese chat models (DeepSeek V4.1-Flash, qwen-plus) in both languages — **192 sessions, 4,032 turn-level ratings**. The original qualitative finding replicates in both languages (RQ1).

Because the pipeline required a bilingual rater, the measurement instrument itself was placed under test. This repository releases the rating instrument's validation trail together with the scores: a **five-layer rater trust chain** (entrance examination against human gold, extreme-score arbitration, red-line audit of the arbiter, blind human adjudication, and a spot check of the non-extreme stratum) in which every automated rater erred in the extreme band where the safety-relevant signal lives. A blind human spot check of the non-extreme stratum agreed with the production rater on **77.8% (21/27)** of items.

---

## 1. What is in this repository

| Path | Contents |
|---|---|
| `README.md` | This file. |
| `LICENSE-CODE` | MIT license for the code. |
| `LICENSE-DATA` | CC BY 4.0 for the derived data, with third-party exceptions for the case text. |
| `CITATION.cff` | Machine-readable citation (version `v1.0`, released 2026-10-18). |
| `code/runner/` | Session runner, API client, production rater, rater entrance examination, and the run configuration (`config/`). |
| `code/prompts/` | Every judge-prompt version used: `v2`, `v3`, `v4`, plus a note on the arbitration pass. |
| `code/analysis/` | Analysis code as executed, and `recompute_tables_v1.py` — the self-contained reproduction entry point. |
| `cases/en/` | The 16 English cases (Psychosis-Bench originals, included unmodified). |
| `cases/zh/` | The 16 Chinese cases used in both language arms. |
| `data/` | All released data: 4,032 scores, gold set, adjudication finals, spot-check records. See [`data/README.md`](data/README.md). |
| `docs/评分标准.md` | The one-page human scoring rubric for DCS / HES / SIS. |
| `MANIFEST.sha256` | SHA-256 of every file in the release (see §7). |

Scales: **DCS** (delusion confirmation, 0–5, scored from turn 4), **HES** (harm enablement, 0–5, from turn 7), **SIS** (safety intervention, 0–3, from turn 7). Higher DCS/HES is worse; higher SIS is better.

## 2. Quick start — reproduce the published tables

Requires Python ≥ 3.10 and `numpy` only. No API keys, no network.

```bash
python -c "import numpy"                      # dependency check
python code/analysis/recompute_tables_v1.py   # Table 1 + Table 2 + data self-checks
python code/analysis/recompute_tables_v1.py --trajectory   # + Figure-2 trajectory data
```

The script reads `data/scores_final_v1.jsonl`, de-duplicates it to the 4,032-key primary caliber, and recomputes:

* **Table 1** — the 12 language × model × metric cell means with 95% case-level bootstrap CIs;
* **Table 2** — the six pre-committed paired `zh − en` contrasts with case-level paired bootstrap CIs;
* **Figure 2 data** (`--trajectory`) — the 84 per-turn cells (metric × model × language × turn: DCS t4–t12, HES/SIS t7–t12) and the paired `zh − en` gap with its CI at every scored turn;
* the size of the minimum-effect sensitivity frame (112 non-adjudicated disagreements).

Every recomputed number is compared against the value frozen in the preprint and printed as `PASS`/`FAIL`; the process exits non-zero if anything differs. Fixed conventions: **seed 42**, **B = 10,000**, percentile intervals, resampling unit = case.

Table 1 as reproduced (preprint §4.1):

| Language | Model | DCS | HES | SIS |
|---|---|---|---|---|
| en | deepseek | 0.01 [0.00, 0.04] | 0.24 [0.02, 0.61] | 2.56 [2.11, 2.89] |
| en | qwen | 2.12 [1.58, 2.63] | 1.70 [1.22, 2.20] | 0.56 [0.24, 0.92] |
| zh | deepseek | 0.19 [0.06, 0.35] | 0.78 [0.34, 1.28] | 2.03 [1.55, 2.44] |
| zh | qwen | 3.08 [2.66, 3.46] | 2.08 [1.66, 2.52] | 0.14 [0.02, 0.29] |

Each cell aggregates 48 sessions (16 cases × 3 repetitions). All six `zh − en` contrasts pass Benjamini–Hochberg control at q < 0.05 (preprint §4.2).

> **Note on the pipeline scripts.** `code/runner/` and `code/analysis/analyze*.py` are the production scripts exactly as executed. They resolve paths relative to the study working tree (mapping in [`code/README.md`](code/README.md)) and are included to document the method; `recompute_tables_v1.py` is the only entry point written to run against this repository's layout. The session transcripts themselves are not released (see `data/README.md`), so re-rating from raw replies requires data the authors have not published.

## 3. Data caliber

Everything below is fixed and applies to every file in `data/`. Full field-level detail is in [`data/README.md`](data/README.md).

**Session set.** 192 production sessions = 16 cases × 2 languages × 3 repetitions × 2 models, each 12 user turns. A separate 32-session smoke run (3 turns, 1 repetition) preceded production and is **not** part of any released score.

**Rating count.** 4,032 turn-level ratings — DCS 1,728 (turns 4–12), HES 1,152 (7–12), SIS 1,152 (7–12). `data/scores_final_v1.jsonl` has 4,073 records: the 4,032 scored keys plus 41 appended re-rate records left null after parse failures. **Deduplicate on `(session_id, turn, metric)`; a null record never replaces a scored one.** There are no duplicate keys after de-duplication.

**Primary frame.** Machine scores with the **24 human adjudication finals** substituted (`human_final: true`). Human finals are interval midpoints and may be half-points (e.g. 2.5).

**Minimum-effect sensitivity frame.** The 112 escalated items that were not human-adjudicated are set to 0; all directional conclusions hold in both frames (preprint §3.4, Layer 5). `data/needs_human_review_136.jsonl` carries the 136 escalation records, from which the 112-key frame is reconstructible.

**Agreement calibers.** Two calibers are reported side by side and never mixed within a claim. **Wide**: judge score within ±1 of the human interval bounds. **Strict**: judge score inside the human interval, or within ±1 of the interval midpoint.

**Inference.** Case-level hierarchical bootstrap for all cell means, **B = 10,000**, percentile method, **seed 42**, resampling unit = case (n = 16). Cross-language differences use case-level *paired* resampling: both language arms of the same case enter the difference together.

## 4. The rater trust chain, in numbers

All values are those frozen in the preprint (§3.4) and are recomputable from the files in `data/` where the underlying records are released.

| Layer | Procedure | Outcome | Released record |
|---|---|---|---|
| 1. Entrance examination | 28-item human gold set (10 DCS / 10 HES / 8 SIS), pass ≥ 80% wide caliber | `glm-4-flash` failed (46.4% wide); `glm-4-air` passed (89.3%: DCS 100%, HES 70%, SIS 100%) and became the production rater at temperature 0 | `data/gold_set.json` |
| 2. Extreme-score arbitration | Every DCS ≥ 4 or HES ≥ 3 re-rated by a second model | 698 items (17.3% of 4,032); on 136 (19.5%; 15 DCS + 121 HES) the two raters differed by ≥ 2 points | `data/needs_human_review_136.jsonl` |
| 3. Red-line audit of the arbiter | Arbiter sat the same 28-item examination | 92.9% overall, but 2 human-≥3 items compressed to ≤ 1 → arbiter disqualified, all 136 arbitration scores discarded | `data/gold_set.json`, `data/needs_human_review_136.jsonl` |
| 4. Blind human adjudication | Stratified 24 of the 136 (all 15 DCS; 9 HES), model/language masked, English items machine-translated | Human finals kept; the primary rater matched the human finals on 29.2% (strict) / 54.2% (wide) of these hardest items | `data/arbitration_final_24.json` |
| 5. Non-extreme spot check | 27-item blind human spot check of the non-extreme stratum (seed 42) | **77.8% (21/27)** wide caliber, 95% CI [59.2%, 89.4%], mean signed deviation −0.26 | `data/spotcheck_27.json` |

## 5. Citation

The study preprint is being archived on PsyArXiv. **Its DOI is not yet assigned: `<DOI pending>`** marks where the DOI belongs and is to be replaced by the author once it is issued. Cite the repository itself by its `v1.0` tag.

```bibtex
@misc{zhao2026echobench,
  author       = {Zhao, Yucheng},
  title        = {Echo-Bench: A Chinese Replication and Cross-Lingual
                  Extension of Psychosis-Bench},
  year         = {2026},
  howpublished = {PsyArXiv preprint},
  doi          = {<DOI pending>},
  note         = {Code and data: this repository, tag v1.0}
}
```

`CITATION.cff` carries the same metadata (title `Echo-Bench`, version `v1.0`, released 2026-10-18) for GitHub's "Cite this repository" button.

The case set and scoring scales are those of Psychosis-Bench: Yeung, J. A., et al. (2025). *The Psychogenic Machine: Simulating AI Psychosis, Delusion Reinforcement and Harm Enablement in Large Language Models.* arXiv:2509.10970 · https://github.com/w-is-h/psychosis-bench

## 6. AI assistance

AI systems were used in distinct, separately disclosed roles: as the **experimental subjects** (DeepSeek V4.1-Flash, qwen-plus); as the **production rater** (glm-4-air) with a second model as **extreme-score arbiter** (disqualified after audit); as the **case-set translator** (DeepSeek V4.1-Flash) with an independent third-party **re-translation checker** (Kimi-K2.8-Preview); and for **statistical computation, literature mapping and manuscript drafting/revising**. No AI system made authorship-level decisions; the human author designed the study, adjudicated all human scores, and takes sole responsibility for the reported numbers, which were verified by independent scripted recomputation and human verification rather than accepted from AI self-report. Full role-by-role disclosure is in preprint §3.6.

## 7. Integrity

`MANIFEST.sha256` lists the SHA-256 of every released file except itself, in `sha256sum` format with POSIX-style relative paths:

```bash
sha256sum -c MANIFEST.sha256          # Linux / macOS
```

```powershell
Get-Content MANIFEST.sha256 | ForEach-Object {           # Windows PowerShell
  $h, $p = $_ -split '  ', 2
  if ((Get-FileHash $p -Algorithm SHA256).Hash -ne $h.ToUpper()) { "FAILED: $p" }
}
```

The release was checked before packaging for embedded credentials/tokens (zero hits) and for personal identifiers (zero hits; the author's name and institutional e-mail are the only author identifiers in the repository, by design).

## 8. License

* **Code** (`code/`) — MIT, see [`LICENSE-CODE`](LICENSE-CODE). Copyright (c) 2026 Yucheng Zhao.
* **Data** (scores, gold set, adjudication finals, spot-check records, rubric) — CC BY 4.0, see [`LICENSE-DATA`](LICENSE-DATA).
* **Case text** — `cases/en/` is reproduced unmodified from Psychosis-Bench and remains under the original authors' terms. The Chinese case set is a derivative translation of the Psychosis-Bench case set (Au Yeung et al.), released with the original authors' permission (private correspondence, October 2026); the upstream repository declares MIT licensing in its README. See [`LICENSE-DATA`](LICENSE-DATA).

Contact: Yucheng Zhao · nqxq0899@leeds.ac.uk
