"""会话执行器：按固定发言序列跑完整会话，JSONL 落盘，支持断点续跑。

用法（项目根目录）:
    python src/runner.py
"""
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from client import ChatClient  # noqa: E402


def load_configs():
    models = yaml.safe_load((ROOT / "config/models.yaml").read_text(encoding="utf-8"))
    exp = yaml.safe_load((ROOT / "config/experiment.yaml").read_text(encoding="utf-8"))
    return models, exp


def session_id(model_name: str, case_id: str, repeat: int, lang: str) -> str:
    return hashlib.md5(f"{lang}|{model_name}|{case_id}|{repeat}".encode()).hexdigest()[:12]


def run_session(client: ChatClient, provider: dict, case: dict, repeat: int, exp: dict) -> dict:
    """跑一条 12 轮会话：每轮把完整历史重发（API 无状态）。"""
    run_cfg = exp["run"]
    messages, turns = [], []
    prompts = case["prompts"][: run_cfg["max_turns"]]
    for i, user_text in enumerate(prompts, 1):
        messages.append({"role": "user", "content": user_text})
        resp = client.chat(provider["model"], messages,
                           temperature=run_cfg["temperature"])
        messages.append({"role": "assistant", "content": resp["content"]})
        turns.append({
            "turn": i, "user": user_text, "assistant": resp["content"],
            "usage": resp["usage"],
        })
    return {
        "session_id": session_id(provider["name"], case["id"], repeat, run_cfg.get("lang", "en")),
        "lang": run_cfg.get("lang", "en"),
        "model_name": provider["name"], "model": resp["model"],
        "case_id": case["id"], "case_name": case["name"],
        "theme": case["theme"], "condition": case["condition"],
        "harm_type": case["harm_type"], "repeat": repeat,
        "temperature": run_cfg["temperature"],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "turns": turns,
    }


def main():
    models_cfg, exp = load_configs()
    run_cfg = exp["run"]
    cases = json.loads((ROOT / run_cfg["cases_file"]).read_text(encoding="utf-8"))["cases"]
    log_dir = ROOT / run_cfg["log_dir"]
    log_dir.mkdir(exist_ok=True)

    providers = [p for p in models_cfg["providers"].values() if p.get("enabled")]
    if not providers:
        print("models.yaml 中没有 enabled: true 的模型。")
        return

    tasks = [(p, c, r) for p in providers for c in cases
             for r in range(run_cfg["repeats"])]

    # 断点续跑：跳过已落盘的 session_id
    done = set()
    for f in log_dir.glob("*.jsonl"):
        for line in f.open(encoding="utf-8"):
            try:
                done.add(json.loads(line)["session_id"])
            except Exception:
                pass
    lang = run_cfg.get("lang", "en")
    tasks = [t for t in tasks
             if session_id(t[0]["name"], t[1]["id"], t[2], lang) not in done]
    print(f"待跑会话: {len(tasks)}（已跳过完成 {len(done)}）")

    clients = {p["name"]: ChatClient(p["base_url"], p["env_key"],
                                     run_cfg["request_timeout"],
                                     run_cfg["max_retries"],
                                     run_cfg["retry_delay"]) for p in providers}
    out_path = log_dir / f"run_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    failed = 0
    with out_path.open("a", encoding="utf-8") as out:
        with ThreadPoolExecutor(max_workers=run_cfg["parallelism"]) as pool:
            futs = {pool.submit(run_session, clients[p["name"]], p, c, r, exp):
                    (p["name"], c["id"], r) for p, c, r in tasks}
            for i, fut in enumerate(as_completed(futs), 1):
                tag = futs[fut]
                try:
                    out.write(json.dumps(fut.result(), ensure_ascii=False) + "\n")
                    out.flush()
                    print(f"[{i}/{len(tasks)}] OK  {tag[0]} | {tag[1]} | rep{tag[2]}")
                except Exception as e:
                    failed += 1
                    print(f"[{i}/{len(tasks)}] FAIL {tag}: {e}")
    print(f"完成。失败 {failed} 条，重跑本脚本可续。日志: {out_path}")


if __name__ == "__main__":
    main()
