# -*- coding: utf-8 -*-
"""pilot 定稿分析：双口径（主口径 / 下界口径）+ 会话级 block bootstrap。

设计要点
--------
1. 双口径
   主口径 = scores_final_v1.jsonl（含 24 条人工终裁覆盖行）
   下界口径 = 主口径中，把「未终裁分歧键」（136 − 24 = 112 个）的 score 置 0（worst case 下界）
2. 统计校正
   turn 级记录在同一会话内自相关，朴素逐条汇总会高估显著性。
   因此所有 CI 用**会话级 block bootstrap**：重采样单位是 session_id，
   抽中一个会话就把它全部记录一起带入；B=10000，百分位法取 2.5%/97.5% 分位。
3. 跨语言差值
   zh 与 en 是**不同会话**（session_id 交集为 0），因此无法做"同一批 session"的
   配对重采样。改为对两侧各自独立重采样后取差值分布——这是在此数据结构下
   唯一正确的做法，报告表3 会明确标注。

不修改旧 analyze.py。
"""
import json
import pathlib
from collections import defaultdict

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "results"
FINAL = RES / "定稿产物"
JUDGE = RES / "judge开发"
SCORES = FINAL / "scores_final_v1.jsonl"
NEEDS = JUDGE / "needs_human_review.jsonl"
TABLES = FINAL / "pilot_final_tables.md"
FIG = FINAL / "dcs_trajectory_final.png"

B = 10000
SEED = 42
METRICS = ("DCS", "HES", "SIS")


# ---------------------------------------------------------------------------
# 载入与去重
# ---------------------------------------------------------------------------
def load_scores() -> list:
    rows = [json.loads(l) for l in SCORES.open(encoding="utf-8") if l.strip()]
    # 同一键可能有「解析失败(None)」与「重评成功」两条；保留有分的那条
    best = {}
    for r in rows:
        k = (r["session_id"], r["turn"], r["metric"])
        if k not in best or (best[k]["score"] is None and r["score"] is not None):
            best[k] = r
    return list(best.values())


def load_lower_bound_keys(rows: list) -> set:
    """未终裁分歧键 = needs_human_review 全部键 − human_final=True 的键。"""
    needs = {tuple(json.loads(l)[f] for f in ("session_id", "turn", "metric"))
             for l in NEEDS.open(encoding="utf-8") if l.strip()}
    hf = {(r["session_id"], r["turn"], r["metric"]) for r in rows if r.get("human_final")}
    return needs - hf


# ---------------------------------------------------------------------------
# block bootstrap（会话级）
# ---------------------------------------------------------------------------
def group_by_session(rows: list, pred) -> tuple:
    """按 pred 过滤后，聚成 {session_id: [scores]}。"""
    g = defaultdict(list)
    for r in rows:
        if pred(r):
            g[r["session_id"]].append(float(r["score"]))
    return g


def boot_mean_ci(sess_scores: dict, rng: np.random.Generator, b: int = B) -> tuple:
    """会话级重采样 -> 均值的 95% CI（百分位法）。"""
    sids = list(sess_scores)
    if not sids:
        return float("nan"), float("nan"), float("nan"), 0, 0
    arrays = [np.asarray(sess_scores[s], dtype=float) for s in sids]
    n_sess = len(sids)
    n_rec = sum(len(a) for a in arrays)
    idx = rng.integers(0, n_sess, size=(b, n_sess))
    means = np.empty(b)
    for i in range(b):
        pick = idx[i]
        means[i] = np.concatenate([arrays[j] for j in pick]).mean()
    return float(np.mean(means)), float(np.percentile(means, 2.5)), \
        float(np.percentile(means, 97.5)), n_sess, n_rec


def boot_diff_ci(sess_a: dict, sess_b: dict, rng: np.random.Generator,
                 b: int = B) -> tuple:
    """两侧独立重采样的差值 (a − b) 分布。

    注：zh/en 的 session_id 无交集，故无法做同一批 session 的配对重采样；
    此处对两侧各自独立重采样，是当前数据结构下唯一正确的做法。
    """
    ka, kb = list(sess_a), list(sess_b)
    if not ka or not kb:
        return float("nan"), float("nan"), float("nan")
    aa = [np.asarray(sess_a[s], dtype=float) for s in ka]
    bb = [np.asarray(sess_b[s], dtype=float) for s in kb]
    na, nb = len(ka), len(kb)
    ia = rng.integers(0, na, size=(b, na))
    ib = rng.integers(0, nb, size=(b, nb))
    d = np.empty(b)
    for i in range(b):
        ma = np.concatenate([aa[j] for j in ia[i]]).mean()
        mb = np.concatenate([bb[j] for j in ib[i]]).mean()
        d[i] = ma - mb
    return float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def fmt(x: float, nd: int = 2) -> str:
    return "—" if x != x else f"{x:.{nd}f}"


def ci_str(lo: float, hi: float) -> str:
    return "—" if lo != lo else f"[{lo:.2f}, {hi:.2f}]"


def main():
    rows = load_scores()
    lb_keys = load_lower_bound_keys(rows)

    # ---- 验收自检 ----
    from collections import Counter
    print("=" * 78)
    print("验收自检")
    print("=" * 78)
    print(f"  记录总数: {len(rows)}（应 4032）")
    print(f"  指标分布: {dict(Counter(r['metric'] for r in rows))}")
    print(f"  human_final=True: {sum(1 for r in rows if r.get('human_final'))} 行（应 24）")
    print(f"  未终裁分歧键: {len(lb_keys)}（应 112）")
    assert len(rows) == 4032, "记录总数不等于 4032"
    assert sum(1 for r in rows if r.get("human_final")) == 24, "human_final 不是 24 行"
    assert len(lb_keys) == 112, "未终裁分歧键不是 112"

    # 下界口径副本
    rows_lb = []
    n_zeroed = 0
    for r in rows:
        r2 = dict(r)
        if (r["session_id"], r["turn"], r["metric"]) in lb_keys:
            r2["score"] = 0
            n_zeroed += 1
        rows_lb.append(r2)
    print(f"  下界口径置 0 的条数: {n_zeroed}")

    # ---- 预先按组切好（两种口径共用会话划分）----
    def prep(rs):
        out = {}
        for lang in ("zh", "en"):
            for model in ("deepseek", "qwen"):
                for m in METRICS:
                    out[(lang, model, m)] = group_by_session(
                        rs, lambda r, l=lang, mo=model, mm=m:
                        r["lang"] == l and r["model_name"] == mo and r["metric"] == mm)
        return out

    G_main, G_lb = prep(rows), prep(rows_lb)

    # ---- 表1/表2：组均值 + CI ----
    print("\n" + "=" * 78)
    print("block bootstrap（会话级）各组 会话数 / 记录数")
    print("=" * 78)
    res_main, res_lb = {}, {}
    for tag, G, store in (("主口径", G_main, res_main), ("下界口径", G_lb, res_lb)):
        rng = np.random.default_rng(SEED)
        for k in sorted(G):
            store[k] = boot_mean_ci(G[k], rng)
        print(f"\n[{tag}]")
        for k in sorted(G):
            mean, lo, hi, ns, nr = store[k]
            print(f"  {k[0]}/{k[1]}/{k[2]:<4} 会话 {ns:>3} | 记录 {nr:>4} | "
                  f"均值 {fmt(mean)} CI {ci_str(lo, hi)}")

    # ---- 表3：跨语言差值 zh − en ----
    diff_main, diff_lb = {}, {}
    for tag, G, store in (("主口径", G_main, diff_main), ("下界口径", G_lb, diff_lb)):
        rng = np.random.default_rng(SEED)
        for model in ("deepseek", "qwen"):
            for m in METRICS:
                store[(model, m)] = boot_diff_ci(G[("zh", model, m)], G[("en", model, m)], rng)

    print("\n" + "=" * 78)
    print("跨语言差值 zh − en")
    print("=" * 78)
    print("  注：zh 与 en 的 session_id 交集为 0（不同会话），无法配对重采样；")
    print("      故对两侧各自独立重采样后取差值分布。")
    for k in sorted(diff_main):
        d, lo, hi = diff_main[k]
        d2, lo2, hi2 = diff_lb[k]
        same = (np.sign(lo) == np.sign(hi)) == (np.sign(lo2) == np.sign(hi2))
        print(f"  {k[0]}/{k[1]}: 主 {d:+.3f} {ci_str(lo,hi)} | 下界 {d2:+.3f} {ci_str(lo2,hi2)} | "
              f"方向一致: {'是' if same else '否'}")

    # ---- 表4：DCS 隐性/显性 ----
    dec = {}
    for tag, rs, store in (("主口径", rows, {}), ("下界口径", rows_lb, {})):
        rng = np.random.default_rng(SEED)
        for cond in ("Explicit", "Implicit"):
            for lang in ("zh", "en"):
                for model in ("deepseek", "qwen"):
                    g = group_by_session(rs, lambda r, c=cond, l=lang, mo=model:
                                         r["condition"] == c and r["lang"] == l
                                         and r["model_name"] == mo and r["metric"] == "DCS")
                    store[(cond, lang, model)] = boot_mean_ci(g, rng)
        dec[tag] = store

    # ---- 图：DCS 轨迹 + CI 带 ----
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    turns = list(range(4, 13))
    for ax, model in zip(axes, ("deepseek", "qwen")):
        for lang, ls in (("zh", "-"), ("en", "--")):
            means, los, his = [], [], []
            for t in turns:
                rng = np.random.default_rng(SEED)
                g = defaultdict(list)
                for r in rows:
                    if (r["metric"] == "DCS" and r["lang"] == lang
                            and r["model_name"] == model and r["turn"] == t):
                        g[r["session_id"]].append(float(r["score"]))
                m, lo, hi, _, _ = boot_mean_ci(g, rng, b=2000)
                means.append(m); los.append(lo); his.append(hi)
            ax.plot(turns, means, ls, label=f"{lang}", linewidth=2)
            ax.fill_between(turns, los, his, alpha=0.18)
        ax.set_title(f"{model} — DCS 轨迹（会话级 95% CI）")
        ax.set_xlabel("轮次")
        ax.grid(alpha=0.3)
        ax.legend()
    axes[0].set_ylabel("DCS 均值")
    fig.suptitle("DCS 轨迹：中文（实线）vs 英文（虚线），阴影为会话级 block bootstrap 95% CI")
    fig.tight_layout()
    fig.savefig(FIG, dpi=150)
    print(f"\n图已保存: {FIG}")

    # ---- 输出表 ----
    L = []
    L.append("# pilot 定稿分析（双口径 + 会话级 block bootstrap）")
    L.append("")
    L.append(f"- 数据: `results/scores_final_v1.jsonl`，唯一键 {len(rows)} 条"
             f"（DCS {sum(1 for r in rows if r['metric']=='DCS')} / "
             f"HES {sum(1 for r in rows if r['metric']=='HES')} / "
             f"SIS {sum(1 for r in rows if r['metric']=='SIS')}）")
    L.append(f"- 人工终裁覆盖行: {sum(1 for r in rows if r.get('human_final'))} 条")
    L.append(f"- 下界口径: 未终裁分歧键 {len(lb_keys)} 个置 0（worst case 下界）")
    L.append(f"- CI: 会话级 block bootstrap，B={B}，百分位法 2.5%/97.5%，random_state={SEED}")
    L.append("")
    L.append("> **方法学说明（跨语言差值）**：zh 与 en 的 session_id 交集为 0，即两种语言是不同会话，"
             "不存在「同一批 session」可供配对重采样。因此表3 采用两侧各自独立重采样后取差值分布，"
             "这是当前数据结构下唯一正确的做法。")
    L.append("")

    def table(store, title):
        L.append(f"## {title}")
        L.append("")
        L.append("| 语言 | 模型 | 指标 | n(记录) | 会话数 | 均值 | 95% CI |")
        L.append("|---|---|---|---|---|---|---|")
        for k in sorted(store):
            mean, lo, hi, ns, nr = store[k]
            L.append(f"| {k[0]} | {k[1]} | {k[2]} | {nr} | {ns} | {fmt(mean)} | {ci_str(lo, hi)} |")
        L.append("")

    table(res_main, "表1：三指标组均值（主口径）")
    table(res_lb, "表2：三指标组均值（下界口径）")

    L.append("## 表3：跨语言差值 zh − en（主口径，附下界口径方向一致性）")
    L.append("")
    L.append("| 模型 | 指标 | zh−en | 95% CI | 是否显著(CI 不含 0) | 下界口径 zh−en | 下界 CI | 方向一致 |")
    L.append("|---|---|---|---|---|---|---|---|")
    all_same = True
    for k in sorted(diff_main):
        d, lo, hi = diff_main[k]
        d2, lo2, hi2 = diff_lb[k]
        sig = not (lo <= 0 <= hi)
        sig2 = not (lo2 <= 0 <= hi2)
        same = sig == sig2
        all_same &= same
        L.append(f"| {k[0]} | {k[1]} | {d:+.3f} | {ci_str(lo, hi)} | "
                 f"{'是' if sig else '否'} | {d2:+.3f} | {ci_str(lo2, hi2)} | "
                 f"{'是' if same else '**否**'} |")
    L.append("")
    if all_same:
        L.append("**所有行的方向一致：是。** 两口径结论方向一致，可写进论文。")
    else:
        L.append("> ⚠️ **出现方向不一致的行（上表加粗）**：两口径结论方向不一致，需谨慎解释，"
                 "原始数据未做任何修改。")
    L.append("")

    L.append("## 表4：DCS 隐性/显性分解（主口径）")
    L.append("")
    L.append("| 条件 | 语言 | 模型 | n(记录) | 会话数 | 均值 | 95% CI |")
    L.append("|---|---|---|---|---|---|---|")
    for k in sorted(dec["主口径"]):
        mean, lo, hi, ns, nr = dec["主口径"][k]
        L.append(f"| {k[0]} | {k[1]} | {k[2]} | {nr} | {ns} | {fmt(mean)} | {ci_str(lo, hi)} |")
    L.append("")
    L.append("### 表4b：同表（下界口径）")
    L.append("")
    L.append("| 条件 | 语言 | 模型 | n(记录) | 会话数 | 均值 | 95% CI |")
    L.append("|---|---|---|---|---|---|---|")
    for k in sorted(dec["下界口径"]):
        mean, lo, hi, ns, nr = dec["下界口径"][k]
        L.append(f"| {k[0]} | {k[1]} | {k[2]} | {nr} | {ns} | {fmt(mean)} | {ci_str(lo, hi)} |")
    L.append("")
    L.append(f"图：`{FIG.name}`（主口径，含会话级 95% CI 阴影带）")
    L.append("")
    TABLES.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"表已保存: {TABLES}")
    print(f"\n表3 方向一致性: {'全部一致' if all_same else '存在不一致（见表格加粗行）'}")


if __name__ == "__main__":
    main()
