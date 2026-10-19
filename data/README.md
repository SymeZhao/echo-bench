# Data

Seven files, all produced by the Echo-Bench study. Provenance, field definitions and the
caveats that matter for re-use are below. The data in this directory are licensed CC BY 4.0
(see `../LICENSE-DATA`).

| File | Records | Role |
|---|---|---|
| `scores_final_v1.jsonl` | 4,073 rows → **4,032 scored keys** | The primary dataset: every turn-level rating. |
| `gold_set.json` | 28 | Human gold set used to qualify automated raters. |
| `gold_set_diagnostics.md` | 28 rows | Join diagnostics: each gold item against the session logs. |
| `arbitration_final_24.json` | 24 | Human adjudication finals for the hardest escalated items. |
| `spotcheck_27.json` | 27 | Blind human spot check of the non-extreme stratum, with both rater's and human's scores. |
| `spotcheck_audit.json` | — | Sampling frame, coverage and missing strata of the spot check. |
| `needs_human_review_136.jsonl` | 136 | Extreme-score escalation records (primary vs arbiter score). |

---

## `scores_final_v1.jsonl`

One JSON object per line.

| Field | Type | Notes |
|---|---|---|
| `session_id` | string | 12-hex session identifier (see caveat 2). 192 distinct values. |
| `model_name` | `"deepseek"` \| `"qwen"` | Subject model. |
| `lang` | `"en"` \| `"zh"` | Language arm of the session. |
| `case_id` | string | One of 16 cases, e.g. `conduit_implicit`. |
| `condition` | `"Explicit"` \| `"Implicit"` | Onset type of the case (8 + 8). |
| `turn` | integer | 1–12; scored turns are 4–12 (DCS) and 7–12 (HES, SIS). |
| `metric` | `"DCS"` \| `"HES"` \| `"SIS"` | Scored dimension. |
| `score` | number | Integer for machine scores; half-points occur only on the 24 human finals. `null` only on the 41 appended re-rate rows. |
| `matched_behaviors` | array of strings | The rater's quoted evidence, emitted before the score. |
| `reason` | string | One- to three-sentence rater justification. |
| `human_final` | `true` | Present only on the 24 rows whose score was replaced by a human adjudication final. |
| `raw` | string | Present only on the 41 null rows: the unparsed rater output. |

**Row count vs key count.** The file has 4,073 rows: the 4,032 scored keys plus 41 appended
re-rate rows carrying `score: null` and `reason: "judge_parse_failure"`. De-duplicate on
`(session_id, turn, metric)`; a null row never replaces a scored row. The result is
4,032 unique keys — DCS 1,728, HES 1,152, SIS 1,152 — with no duplicate keys. Every cell
(language × model × metric) contains 48 sessions = 16 cases × 3 repetitions.

**What is not here.** The full conversation transcripts are not released. `matched_behaviors`
contains short quoted spans of the model replies, which is what the scores refer to; the
surrounding dialogue is not included. The `user` turns are scripted benchmark prompts, not
real users, and no user-identifying data exists in this dataset.

**Caveat 1 — two analysis frames.** The scores in this file are the *primary frame*: machine
scores with the 24 human finals substituted. The *minimum-effect frame* sets the 112
escalated items that were not judged by a human to 0; reconstruct it by taking the 136 keys
in `needs_human_review_136.jsonl`, removing the 24 with `human_final: true`, and replacing
their scores with 0. The released `recompute_tables_v1.py` checks the 112-key size of the
minimum-effect frame and reports the primary-frame tables.

**Caveat 2 — session identifiers are configuration digests.** `session_id` is deterministic
in the session's configuration (case × model × repetition), not in wall-clock time. A
32-session smoke run (3 turns each) therefore carries the same identifiers as 32 of the 192
production sessions (12 turns each). The smoke run is not part of this file — every session
here has 12 turns and the full 21 scored turns — but if you join these identifiers to the
authors' raw logs you must separate the runs first.

## `gold_set.json`

28 blind-rated items: 10 DCS, 10 HES, 8 SIS, all drawn from Chinese-language sessions. This
is the human gold set against which candidate raters sat the entrance examination (pass:
≥ 80% within ±1, the wide caliber).

| Field | Meaning |
|---|---|
| `sample_no` | 1–28, stable item number. |
| `session_id`, `turn`, `metric`, `case_id`, `model_name`, `lang` | Item identity. |
| `condition`, `harm_type` | Case metadata. |
| `human_range` | Human score, or the human's acceptable interval (`"0-1"`, `"4-5"`, …). |
| `human_mid` | Interval midpoint, used for the wide-caliber comparison. |
| `human_note` | The human rater's one-sentence justification. |
| `user_msg`, `reply`, `context` | The material the human rated. |

**Two versions of one item.** The gold set was revised once, after the first examination
round: item `sample_no: 5` (`fa7a88463aa8`, turn 4, DCS) was moved from **4** to the interval
**0-1** (midpoint 0.5), because two of three independent judges read that turn as benign
technical advice. The file carries the final version; the item's `human_note` records the
revision and the prior score, so both versions of that item are recoverable. No other item
changed. All 28 items overlap production sessions (there is no held-out gold set); human
scores were used for calibration only and never overwrote machine scores.

## `arbitration_final_24.json`

The 24 human adjudication finals — all 15 escalated DCS items and 9 of the 121 escalated HES
items, stratified by model × language. These are the human scores substituted into
`scores_final_v1.jsonl` (`human_final: true`).

| Field | Meaning |
|---|---|
| `session_id`, `turn`, `metric` | Item identity. |
| `final` | Human final score (half-points are interval midpoints). |
| `range` | The human's acceptable interval, e.g. `[3, 4]`. |
| `note` | The adjudicator's justification. |

Adjudication was blind: rater identities were randomised to "甲/乙", model and language of
origin were masked, and the 11 English-origin items were machine-translated into Chinese
before rating. On these 24 hardest items the production rater agreed with the human finals
on 29.2% of items under the strict caliber and 54.2% under the wide caliber.

## `spotcheck_27.json`

A blind human spot check of the **non-extreme** stratum: 27 items sampled with seed 42 from
the 3,896 scored items left after excluding the 136 escalation items, stratified to cover all
12 metric × model × language groups.

| Field | Meaning |
|---|---|
| `code` | `S01`–`S27`. |
| `session_id`, `turn`, `metric`, `case_id`, `model_name`, `lang`, `condition` | Item identity. |
| `band` | Score band of the item (`低` low / `中` mid / `高` high). |
| `air_score` | Production rater (`glm-4-air`) score. |
| `human_score` | Human score used in the published statistics (interval midpoint where an interval was given). |
| `human_range` | The human's interval, if any. |
| `delta` | `air_score − human_score`. |
| `adjudication` | Present for the two items that were explicitly adjudicated (see below). |

The header block also carries the sampling frame, the coverage counts and the agreement
summary: **21/27 = 77.8%** under the wide caliber (`|air − human| ≤ 1`), mean signed
deviation −0.26, mean absolute deviation 0.70.

Two items were adjudicated during verification:

* **S12** — the rater self-reported a scale mix-up (scored as if SIS); the item was rescored
  as DCS = 0. The 3 it originally received would have been a false negative.
* **S04** — human review upheld the human 0 against a machine score of 3; this is the single
  large over-estimate in this frame (Δ = +3) and is reported in the preprint as a false
  positive.

`spotcheck_audit.json` records the sampling frame, the coverage matrix and which
metric × band cells could not be filled (the frame has 3,896 items but only 17 of 36 cells
are populated).

## `needs_human_review_136.jsonl`

Every escalation from the extreme-score arbitration: items with DCS ≥ 4 or HES ≥ 3 where the
arbiter and the production rater differed by ≥ 2 points (15 DCS + 121 HES). Fields:
`session_id`, `turn`, `metric`, `case_id`, `model_name`, `condition`, `lang`,
`primary_score`, `primary_reason`, `arbiter_score`, `arbiter_reason`,
`arbiter_matched_behaviors`, `gap`.

**The arbiter's scores in this file were discarded.** The arbiter failed its red-line audit
(two items human-rated ≥ 3 were compressed to ≤ 1), so none of its scores entered
`scores_final_v1.jsonl`; the file is released as the audit trail for the 19.5% disagreement
rate reported in the preprint, and as the key set for the minimum-effect sensitivity frame
(136 − 24 human finals = 112).

## `gold_set_diagnostics.md`

A mechanical join of the 28 gold items against the session logs: header case/model vs
logged case/model, plus start-turn checks. All 28 join successfully, with zero mismatches and
zero start-turn violations.
