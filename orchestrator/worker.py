"""
常驻消费器 —— 无人值守批量执行。

设计要点（来自生产实践）：
  1. LLM 不参与本循环。只消费账本里的确定性任务。
  2. 队列深度 1：ComfyUI 单进程串行，塞满队列会让超时判断失真。
  3. 双超时：总时长 + WS 静默时长。卡死只能杀进程，静默检测是唯一手段。
  4. 失败分级：VALIDATION_FAILED 不重试；OOM/TIMEOUT 降级重试。
  5. 每个 job 结束主动 /free 清显存。
  6. 归档用 {job_id}_{shot_id}，不依赖 ComfyUI 自动编号。

用法：
  python orchestrator/worker.py --loop                 # 常驻
  python orchestrator/worker.py --tick                 # 跑一批就退（配 cron）
  python orchestrator/worker.py --once --workflow w.json --set PROMPT=... --set SEED=42
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from comfy.adapter.comfy_client import ComfyClient, ComfyError, FATAL_CODES  # noqa: E402
from orchestrator import job_ledger as ledger  # noqa: E402

OUT_ROOT = ROOT / "out"
LOG_DIR = ROOT / "out" / "_logs"


# --------------------------------------------------------------------------- #
def _slot(graph: dict, key: str, value) -> dict:
    """把值写进 API 图的指定节点输入。key 形如 '30.prompt' 或 'PROMPT'。"""
    KEYMAP = {
        "PROMPT": ("30", "prompt"), "SEED": ("42", "noise_seed"),
        "STEPS": ("41", "steps"), "WIDTH": ("30", "width"),
        "HEIGHT": ("30", "height"), "LENGTH": ("30", "length"),
        "MODE": ("30", "mode"), "REF_IMAGES": ("31", "image_paths"),
        "JOB_ID": ("60", "filename_prefix"), "SAMPLER": ("40", "sampler_name"),
    }
    node_id, inp = KEYMAP.get(key, (None, None))
    if node_id is None and "." in key:
        node_id, inp = key.split(".", 1)
    if node_id is None:
        raise SystemExit(f"未知槽位 {key}；可用：{list(KEYMAP)}")
    if node_id not in graph:
        raise SystemExit(f"图中没有节点 {node_id}（可能被条件剔除）")
    graph[node_id]["inputs"][inp] = value
    return graph


def run_one(client: ComfyClient, job: dict, hard_timeout: int, idle_timeout: int) -> bool:
    jid = job["job_id"]
    graph = json.loads(Path(job["workflow"]).read_text(encoding="utf-8"))

    prefix = f"{jid}_{job.get('shot_id') or 'shot'}"
    _slot(graph, "JOB_ID", prefix)
    if job.get("prompt"):
        _slot(graph, "PROMPT", job["prompt"])
    if job.get("seed") is not None:
        _slot(graph, "SEED", int(job["seed"]))
    if job.get("steps"):
        _slot(graph, "STEPS", int(job["steps"]))
    if job.get("mode"):
        _slot(graph, "MODE", job["mode"])
    if job.get("ref_images"):
        _slot(graph, "REF_IMAGES", job["ref_images"])
    if job.get("res"):
        w, h = job["res"].lower().split("x")
        _slot(graph, "WIDTH", int(w))
        _slot(graph, "HEIGHT", int(h))

    outdir = OUT_ROOT / jid
    outdir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    events = []
    t0 = time.time()
    try:
        res = client.run(
            graph, retries=2, hard_timeout=hard_timeout, idle_timeout=idle_timeout,
            on_event=lambda m: events.append({"t": round(time.time() - t0, 2), **m}),
        )
    except ComfyError as e:
        if e.code in FATAL_CODES:
            # 不可重试：节点缺失 / 图校验失败 → 立即失败并告警
            ledger.mark(jid, "failed", error=f"[{e.code}] {e}")
        else:
            ledger.mark(jid, "failed", error=f"[{e.code}] {e} (重试已耗尽)")
        _dump_log(jid, graph, events, e)
        print(f"✗ {jid}: [{e.code}] {e}")
        return False

    for name, blob in res.files:
        (outdir / name).write_bytes(blob)

    vram = None
    try:
        st = client.system_stats()
        dev = (st.get("devices") or [{}])[0]
        vram = round(dev.get("vram_total", 0) / (1024 ** 3), 1)
    except Exception:
        pass

    ledger.mark(jid, "done", prompt_id=res.prompt_id, elapsed_s=res.elapsed_s,
                peak_vram_gb=vram, output_dir=str(outdir))
    _dump_log(jid, graph, events, None)
    print(f"✓ {jid} ({res.elapsed_s:.1f}s, {len(res.files)} 文件) -> {outdir}")

    # 主动清显存
    client.free()
    return True


def _dump_log(jid: str, graph: dict, events: list, err) -> None:
    """失败时把当时的 API JSON 一并落盘，保证可复现。"""
    (LOG_DIR / f"{jid}.graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    (LOG_DIR / f"{jid}.events.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events), encoding="utf-8")
    if err:
        (LOG_DIR / f"{jid}.error.txt").write_text(str(err), encoding="utf-8")


# --------------------------------------------------------------------------- #
def tick(client: ComfyClient, batch: int, hard_timeout: int, idle_timeout: int) -> int:
    jobs = ledger.claim(batch)
    if not jobs:
        return 0
    ok = 0
    for j in jobs:
        if not j.get("workflow"):
            ledger.mark(j["job_id"], "failed", error="缺少 workflow 字段")
            continue
        ok += run_one(client, j, hard_timeout, idle_timeout)
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1:8188")
    ap.add_argument("--loop", action="store_true", help="常驻")
    ap.add_argument("--tick", action="store_true", help="跑一批就退")
    ap.add_argument("--once", action="store_true", help="单任务（--workflow）")
    ap.add_argument("--batch", type=int, default=1, help="每批领取数（建议 1）")
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--hard-timeout", type=int, default=1800)
    ap.add_argument("--idle-timeout", type=int, default=300)
    ap.add_argument("--workflow")
    ap.add_argument("--set", action="append", default=[], help="K=V，见 _slot KEYMAP")
    a = ap.parse_args()

    client = ComfyClient(a.host)
    if not client.is_alive():
        print(f"ComfyUI 不在线（{a.host}）", file=sys.stderr)
        sys.exit(2)

    if a.once:
        if not a.workflow:
            sys.exit("--once 需要 --workflow")
        kv = dict(s.split("=", 1) for s in a.set)
        job = {"job_id": f"once_{int(time.time())}", "shot_id": "s0",
               "workflow": a.workflow, "prompt": kv.get("PROMPT", ""),
               "seed": int(kv["SEED"]) if "SEED" in kv else 0,
               "steps": int(kv["STEPS"]) if "STEPS" in kv else None,
               "mode": kv.get("MODE"), "res": kv.get("RES"),
               "ref_images": kv.get("REF_IMAGES", "").split(",") if kv.get("REF_IMAGES") else None}
        sys.exit(0 if run_one(client, job, a.hard_timeout, a.idle_timeout) else 1)

    n_reset = ledger.reset_stale()
    if n_reset:
        print(f"断点续跑：{n_reset} 条 running -> pending")

    total = 0
    while True:
        try:
            total += tick(client, a.batch, a.hard_timeout, a.idle_timeout)
        except KeyboardInterrupt:
            print("\n已停止")
            break
        except Exception as e:                       # 单批异常不拖垮常驻循环
            print(f"批次异常：{e}", file=sys.stderr)
            time.sleep(a.interval * 2)
        if a.tick and not a.loop:
            break
        st = ledger.stats()
        if st["pending"] == 0 and st["running"] == 0:
            print(f"任务清空，共完成 {total} 个。剩余：{st}")
            break
        time.sleep(a.interval)

    print(f"完成 {total} 个任务。账本：{ledger.stats()}")


if __name__ == "__main__":
    main()
