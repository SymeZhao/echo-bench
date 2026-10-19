"""汇总分析：均值表、显式/隐式分组、轨迹曲线图。

用法（项目根目录）:
    python src/analyze.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def main():
    scores_path = ROOT / "results/scores.jsonl"
    if not scores_path.exists():
        print("未找到 results/scores.jsonl，请先运行 judge.py")
        return
    df = pd.read_json(scores_path, lines=True)
    df = df.dropna(subset=["score"])
    if "lang" not in df.columns:
        df["lang"] = "en"

    # 1. 语言 × 模型 × 指标 均值总表
    summary = (df.groupby(["lang", "model_name", "metric"])["score"]
               .agg(["mean", "std", "count"]).round(3))
    print("=== 语言 × 模型 × 指标 总表 ===")
    print(summary.to_string())

    # 2. 显式 vs 隐式
    by_cond = (df.groupby(["lang", "model_name", "condition", "metric"])["score"]
               .mean().unstack("condition").round(3))
    print("\n=== 显式/隐式 分组均值 ===")
    print(by_cond.to_string())

    summary.to_csv(ROOT / "results" / "归档" / "summary_by_model.csv")
    by_cond.to_csv(ROOT / "results" / "归档" / "summary_by_condition.csv")

    # 3. 轨迹曲线：DCS 随轮次变化，每（语言×模型）一条线
    fig, ax = plt.subplots(figsize=(9, 5))
    dcs = df[df["metric"] == "DCS"]
    for (lang, model), g in dcs.groupby(["lang", "model_name"]):
        traj = g.groupby("turn")["score"].mean()
        style = "-" if lang == "zh" else "--"
        ax.plot(traj.index, traj.values, marker="o", linestyle=style,
                label=f"{model} ({lang})")
    ax.set_xlabel("轮次")
    ax.set_ylabel("DCS 均值（妄想确认度）")
    ax.set_title("妄想确认度随轮次的轨迹（实线=中文，虚线=英文）")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ROOT / "results" / "归档" / "dcs_trajectory.png", dpi=150)
    print("\n图表已保存: results/归档/dcs_trajectory.png")


if __name__ == "__main__":
    main()
