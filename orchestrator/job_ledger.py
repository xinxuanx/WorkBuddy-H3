"""
作业账本 —— SQLite。无人值守批量生产的核心：可断点续跑、可对账、可抽样质检。

状态机：pending -> running -> done / failed
启动时把 running 转回 pending（进程被杀也不丢任务）。

用法：
  python orchestrator/job_ledger.py import shots.jsonl
  python orchestrator/job_ledger.py stats
  python orchestrator/job_ledger.py next --n 5
  python orchestrator/job_ledger.py mark <job_id> running|done|failed [--err "..."]
  python orchestrator/job_ledger.py sample --rate 0.1 --out qc.jsonl
  python orchestrator/job_ledger.py apply-qc qc_result.jsonl
  python orchestrator/job_ledger.py reset-stale
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "orchestrator" / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  job_id       TEXT PRIMARY KEY,
  shot_id      TEXT,
  mode         TEXT,
  variant      TEXT,
  workflow     TEXT,
  prompt       TEXT,
  ref_images   TEXT,
  seed         INTEGER,
  steps        INTEGER,
  res          TEXT,
  status       TEXT NOT NULL DEFAULT 'pending',
  attempts     INTEGER NOT NULL DEFAULT 0,
  prompt_id    TEXT,
  elapsed_s    REAL,
  peak_vram_gb REAL,
  output_dir   TEXT,
  qc           TEXT,
  error        TEXT,
  created_at   REAL,
  updated_at   REAL
);
CREATE INDEX IF NOT EXISTS idx_status ON jobs(status);
"""


def conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    return c


def upsert(rows: list[dict]) -> int:
    c = conn()
    now = time.time()
    n = 0
    for r in rows:
        if "job_id" not in r:
            raise SystemExit("每条任务必须有 job_id")
        r.setdefault("status", "pending")
        r.setdefault("created_at", now)
        r["updated_at"] = now
        keys = [k for k in r if k in _COLS]
        c.execute(
            f"INSERT INTO jobs ({','.join(keys)}) VALUES ({','.join('?' * len(keys))}) "
            f"ON CONFLICT(job_id) DO UPDATE SET {','.join(f'{k}=excluded.{k}' for k in keys if k != 'job_id')}",
            [json.dumps(r[k]) if isinstance(r[k], (list, dict)) else r[k] for k in keys],
        )
        n += 1
    c.commit()
    c.close()
    return n


_COLS = {"job_id", "shot_id", "mode", "variant", "workflow", "prompt", "ref_images",
         "seed", "steps", "res", "status", "attempts", "prompt_id", "elapsed_s",
         "peak_vram_gb", "output_dir", "qc", "error", "created_at", "updated_at"}


def _row(d: tuple) -> dict:
    c = conn()
    c.row_factory = sqlite3.Row
    return c


def stats() -> dict:
    c = conn()
    out = {r[0]: r[1] for r in c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")}
    for s in ("pending", "running", "done", "failed"):
        out.setdefault(s, 0)
    c.close()
    return out


def claim(n: int = 1) -> list[dict]:
    """原子领取 pending 任务并置为 running。"""
    c = conn()
    c.row_factory = sqlite3.Row
    ids = [r["job_id"] for r in c.execute(
        "SELECT job_id FROM jobs WHERE status='pending' ORDER BY created_at LIMIT ?", (n,))]
    now = time.time()
    for jid in ids:
        c.execute("UPDATE jobs SET status='running', attempts=attempts+1, updated_at=? "
                  "WHERE job_id=?", (now, jid))
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM jobs WHERE job_id IN (%s)" % ",".join("?" * len(ids)), ids)] if ids else []
    c.commit()
    c.close()
    return rows


def mark(job_id: str, status: str, *, prompt_id: str | None = None,
         elapsed_s: float | None = None, peak_vram_gb: float | None = None,
         output_dir: str | None = None, error: str | None = None) -> None:
    c = conn()
    c.execute("UPDATE jobs SET status=?, prompt_id=COALESCE(?,prompt_id), "
              "elapsed_s=COALESCE(?,elapsed_s), peak_vram_gb=COALESCE(?,peak_vram_gb), "
              "output_dir=COALESCE(?,output_dir), error=?, updated_at=? WHERE job_id=?",
              (status, prompt_id, elapsed_s, peak_vram_gb, output_dir, error,
               time.time(), job_id))
    c.commit()
    c.close()


def reset_stale() -> int:
    c = conn()
    cur = c.execute("UPDATE jobs SET status='pending' WHERE status='running'")
    n = cur.rowcount
    c.commit()
    c.close()
    return n


def sample(rate: float, out: Path) -> int:
    c = conn()
    c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute("SELECT * FROM jobs WHERE status='done' AND qc IS NULL")]
    c.close()
    k = max(1, int(len(rows) * rate))
    picked = rows[::max(1, len(rows) // k)][:k]
    out.write_text("\n".join(json.dumps({
        "job_id": r["job_id"], "shot_id": r["shot_id"], "mode": r["mode"],
        "output_dir": r["output_dir"], "seed": r["seed"], "q": ""
    }, ensure_ascii=False) for r in picked), encoding="utf-8")
    return len(picked)


def apply_qc(path: Path) -> int:
    c = conn()
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        verdict = r.get("q", "pass")
        c.execute("UPDATE jobs SET qc=?, status=CASE WHEN ?='retry' THEN 'pending' ELSE status END, "
                  "error=COALESCE(?, error), updated_at=? WHERE job_id=?",
                  (verdict, verdict, r.get("reason"), time.time(), r["job_id"]))
        n += 1
    c.commit()
    c.close()
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("import")
    p.add_argument("jsonl")

    sub.add_parser("stats")

    p = sub.add_parser("next")
    p.add_argument("--n", type=int, default=1)

    p = sub.add_parser("mark")
    p.add_argument("job_id")
    p.add_argument("status", choices=["pending", "running", "done", "failed"])
    p.add_argument("--prompt-id"); p.add_argument("--elapsed", type=float)
    p.add_argument("--vram", type=float); p.add_argument("--outdir")
    p.add_argument("--err")

    p = sub.add_parser("sample")
    p.add_argument("--rate", type=float, default=0.1)
    p.add_argument("--out", default="qc_batch.jsonl")

    p = sub.add_parser("apply-qc")
    p.add_argument("jsonl")

    sub.add_parser("reset-stale")

    a = ap.parse_args()

    if a.cmd == "import":
        rows = [json.loads(l) for l in Path(a.jsonl).read_text(
            encoding="utf-8").splitlines() if l.strip()]
        print(f"导入 {upsert(rows)} 条")
    elif a.cmd == "stats":
        print(json.dumps(stats(), indent=2))
    elif a.cmd == "next":
        print(json.dumps(claim(a.n), ensure_ascii=False, indent=2))
    elif a.cmd == "mark":
        mark(a.job_id, a.status, prompt_id=a.prompt_id, elapsed_s=a.elapsed,
             peak_vram_gb=a.vram, output_dir=a.outdir, error=a.err)
        print("ok")
    elif a.cmd == "sample":
        print(f"抽样 {sample(a.rate, Path(a.out))} 条 -> {a.out}")
    elif a.cmd == "apply-qc":
        print(f"应用 {apply_qc(Path(a.jsonl))} 条")
    elif a.cmd == "reset-stale":
        print(f"重置 {reset_stale()} 条 running -> pending")


if __name__ == "__main__":
    main()
