"""
ComfyUI 客户端 —— L2 适配层

职责（且仅此）：
  - 提交任务 / WebSocket 监听 / 取回产物 / 释放显存 / 中断
  - 失败分级与重试
不理解任何业务语义，不含任何模型参数。

依赖：pip install websocket-client requests
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests

try:
    import websocket  # websocket-client
except ImportError:  # pragma: no cover
    websocket = None


class ComfyError(Exception):
    def __init__(self, code: str, msg: str, detail: Any = None):
        super().__init__(f"[{code}] {msg}")
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------- #
# 失败分级
# --------------------------------------------------------------------------- #
FATAL_CODES = {"VALIDATION_FAILED", "INVALID_ARGS", "NOT_FOUND"}   # 不可重试
RETRY_CODES = {"TIMEOUT", "OOM", "COMFY_DOWN", "QUEUE_FULL"}       # 可重试（需降级）


@dataclass
class JobResult:
    prompt_id: str
    files: list[tuple[str, bytes]] = field(default_factory=list)
    elapsed_s: float = 0.0
    attempts: int = 1


class ComfyClient:
    """ComfyUI HTTP + WebSocket 客户端。"""

    def __init__(self, host: str = "127.0.0.1:8188", client_id: str | None = None,
                 timeout: int = 30):
        self.base = f"http://{host}"
        self.ws_base = f"ws://{host}"
        self.client_id = client_id or str(uuid.uuid4())
        self.timeout = timeout

    # ---------------- 基础 ---------------- #
    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def get(self, path: str, **kw) -> Any:
        r = requests.get(self._url(path), timeout=self.timeout, **kw)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, payload: Any = None, **kw) -> Any:
        r = requests.post(self._url(path), json=payload or {}, timeout=self.timeout, **kw)
        return r

    # ---------------- 探测 ---------------- #
    def system_stats(self) -> dict:
        return self.get("/system_stats")

    def object_info(self, node_class: str | None = None) -> dict:
        return self.get(f"/object_info/{node_class}" if node_class else "/object_info")

    def features(self) -> dict:
        try:
            return self.get("/features")
        except Exception:
            return {}

    def queue(self) -> dict:
        return self.get("/queue")

    def is_alive(self) -> bool:
        try:
            self.system_stats()
            return True
        except Exception:
            return False

    # ---------------- 上传 ---------------- #
    def upload_image(self, file_path: str | Path, subfolder: str = "",
                     overwrite: bool = True) -> str:
        """POST /upload/image，返回 ComfyUI 侧的文件名。"""
        p = Path(file_path)
        if not p.exists():
            raise ComfyError("NOT_FOUND", f"image not found: {p}")
        with p.open("rb") as f:
            r = requests.post(
                self._url("/upload/image"),
                files={"image": (p.name, f, "image/png")},
                data={"subfolder": subfolder, "overwrite": str(overwrite).lower()},
                timeout=120,
            )
        if r.status_code != 200:
            raise ComfyError("INVALID_ARGS", f"upload failed: {r.text}")
        return r.json().get("name", p.name)

    # ---------------- 提交 ---------------- #
    def submit(self, api_graph: dict, prompt_id: str | None = None) -> str:
        """POST /prompt。客户端预生成 prompt_id，便于对账/去重/断点续跑。"""
        pid = prompt_id or str(uuid.uuid4())
        r = self.post("/prompt", {"prompt": api_graph, "client_id": self.client_id,
                                  "prompt_id": pid})
        if r.status_code == 400:
            body = r.json()
            # 图校验失败 / 节点缺失 —— 不可重试
            raise ComfyError(
                "VALIDATION_FAILED",
                "workflow rejected by ComfyUI (missing node or bad graph)",
                {"node_errors": body.get("node_errors"), "error": body.get("error")},
            )
        if r.status_code != 200:
            raise ComfyError("COMFY_DOWN", f"/prompt -> {r.status_code}: {r.text[:400]}")
        return pid

    # ---------------- 监听 ---------------- #
    def wait(self, prompt_id: str, hard_timeout: int = 1800, idle_timeout: int = 300,
             on_event: Callable[[dict], None] | None = None) -> None:
        """WebSocket 监听，双超时：总时长 + 无进度静默时长。

        ComfyUI 卡死只能杀进程，静默检测是唯一手段。
        """
        if websocket is None:
            raise ComfyError("INVALID_ARGS", "websocket-client not installed")

        ws = websocket.WebSocket()
        ws.connect(f"{self.ws_base}/ws?clientId={self.client_id}", timeout=self.timeout)
        deadline = time.time() + hard_timeout
        last = time.time()
        try:
            while True:
                ws.settimeout(30)
                try:
                    out = ws.recv()
                except Exception:
                    if time.time() > deadline:
                        raise ComfyError("TIMEOUT", f"hard timeout: {prompt_id}")
                    if time.time() - last > idle_timeout:
                        raise ComfyError("TIMEOUT", f"idle timeout (no WS event): {prompt_id}")
                    continue

                if not isinstance(out, str):
                    continue                      # 二进制预览帧
                msg = json.loads(out)
                if on_event:
                    on_event(msg)

                if msg.get("type") == "executing":
                    last = time.time()
                    d = msg.get("data", {})
                    if d.get("prompt_id") == prompt_id and d.get("node") is None:
                        return                     # 完成
                elif msg.get("type") == "progress":
                    last = time.time()
                elif msg.get("type") == "execution_error":
                    raise ComfyError("OOM", f"execution error: {msg.get('data')}")
        finally:
            try:
                ws.close()
            except Exception:
                pass

    # ---------------- 取回 ---------------- #
    def fetch(self, prompt_id: str) -> list[tuple[str, bytes]]:
        """从 /history 取产物索引，再从 /view 下载。"""
        try:
            hist = self.get(f"/history/{prompt_id}")
        except Exception as e:
            raise ComfyError("NOT_FOUND", f"history unavailable: {e}")

        node = hist.get(prompt_id)
        if not node:
            raise ComfyError("NOT_FOUND", f"no history for {prompt_id}")

        files: list[tuple[str, bytes]] = []
        for out in node.get("outputs", {}).values():
            for key in ("images", "gifs", "videos"):
                for f in out.get(key, []):
                    params = {"filename": f["filename"],
                              "subfolder": f.get("subfolder", ""),
                              "type": f.get("type", "output")}
                    r = requests.get(self._url("/view"), params=params, timeout=300)
                    if r.status_code == 200:
                        files.append((f["filename"], r.content))
        if not files:
            raise ComfyError("NOT_FOUND", f"no outputs for {prompt_id}")
        return files

    # ---------------- 控制 ---------------- #
    def interrupt(self) -> None:
        try:
            self.post("/interrupt")
        except Exception:
            pass

    def free(self, unload_models: bool = True, free_memory: bool = True) -> None:
        try:
            self.post("/free", {"unload_models": unload_models, "free_memory": free_memory})
        except Exception:
            pass

    # ---------------- 组合：一次完整 run ---------------- #
    def run(self, api_graph: dict, retries: int = 2, hard_timeout: int = 1800,
            idle_timeout: int = 300, prompt_id: str | None = None,
            on_event: Callable[[dict], None] | None = None) -> JobResult:
        """提交 → 监听 → 取回，含重试分级。

        不可重试：VALIDATION_FAILED（图校验失败 / 节点缺失）—— 立即抛
        可重试：TIMEOUT / OOM —— 先 interrupt + free 再重试
        """
        t0 = time.time()
        last_err: ComfyError | None = None
        for attempt in range(retries + 1):
            try:
                pid = self.submit(api_graph, prompt_id=prompt_id)
                self.wait(pid, hard_timeout=hard_timeout, idle_timeout=idle_timeout,
                          on_event=on_event)
                files = self.fetch(pid)
                return JobResult(prompt_id=pid, files=files,
                                 elapsed_s=time.time() - t0, attempts=attempt + 1)
            except ComfyError as e:
                last_err = e
                if e.code in FATAL_CODES:
                    raise                       # 不重试
                # 超时/OOM：先中断再清显存
                self.interrupt()
                self.free()
                if attempt == retries:
                    raise
                time.sleep(3 * (attempt + 1))
        raise last_err or ComfyError("COMFY_DOWN", "unreachable")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main() -> None:  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(description="ComfyUI client smoke test")
    ap.add_argument("--host", default="127.0.0.1:8188")
    ap.add_argument("--workflow", help="API-format workflow JSON")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    c = ComfyClient(a.host)
    if a.status or not a.workflow:
        print(json.dumps(c.system_stats(), indent=2, ensure_ascii=False))
        return

    graph = json.loads(Path(a.workflow).read_text(encoding="utf-8"))
    res = c.run(graph)
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, blob in res.files:
        (outdir / name).write_bytes(blob)
        print(f"saved {outdir / name} ({len(blob)} bytes)")
    print(f"prompt_id={res.prompt_id} elapsed={res.elapsed_s:.1f}s attempts={res.attempts}")


if __name__ == "__main__":
    _main()
