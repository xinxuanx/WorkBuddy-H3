# 04 — Agent ↔ ComfyUI 交互协议

> 参考实现见 `comfy/adapter/comfy_client.py` 与 `comfy/build_workflow.py`。

---

## 1. 五层架构

```
L5  Agent（Hermes / OpenClaw / Claude Code / 任意框架）
     │  遵循 agent/TOOL-CONTRACT.md
L4  Agent 适配层（MCP server / CLI / HTTP OpenAPI）  ← 换 Agent 只改这层
L3  Orchestrator（作业账本 + 常驻 worker）          ← orchestrator/
L2  ComfyUI 适配层（HTTP + WebSocket）              ← comfy/adapter/
L1  ComfyUI Runtime（comfy-cli 托管）               ← L0 模型与节点
```

**核心原则：LLM 不进每视频的循环。**
Agent 只在阶段边界介入（剧本 → 分镜 → 设定图提示词 → H3 prompt → 抽检 → 打包），
批量执行由常驻 worker 消费任务表完成。

---

## 2. ComfyUI API 端点（实测 v0.38.0）

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/prompt` | 提交任务（body: `{prompt, client_id, prompt_id}`） |
| GET | `/ws` | WebSocket 进度与完成事件 |
| GET | `/history` · `/history/{prompt_id}` | 取执行结果与产物索引 |
| GET | `/queue` | 查看 running / pending |
| POST | `/interrupt` | 中断当前执行 |
| POST | `/free` | 释放显存 `{unload_models, free_memory}` |
| GET | `/view?filename=&subfolder=&type=` | 下载产物 |
| POST | `/upload/image` | 上传参考图（multipart） |
| GET | `/object_info` · `/object_info/{node}` | 发现节点 schema |
| GET | `/system_stats` | 显存/内存采样（可观测性） |
| GET | `/features` · `/models` · `/models/{folder}` | 能力探测 |
| GET/POST | `/api/jobs` · `/api/jobs/{id}` · `/api/jobs/{id}/cancel` | **新增** Job API |

---

## 3. 集成范式对比（为什么这么选）

| 范式 | 优点 | 缺点 | 本项目 |
|---|---|---|---|
| ① 原生 HTTP + WS | 零依赖、延迟最低、完全掌控队列/重试 | 要自己写胶水 | ✅ **主** |
| ② comfy-cli | 环境/节点/模型管理一条龙，全命令有 `--json` | 每次 shell out 子进程 | ✅ 环境初始化 |
| ③ MCP 包一层 | Agent 原生可发现 | stdio 长任务阻塞；beta | 🔶 未来适配层 |
| ④ **API JSON 模板 + 占位符替换** | 官方示例就是这么干；确定性最好、最省 token | Agent 需知道节点 ID | ✅ **主** |
| ⑤ 桥接库 comfy-sdk / ComfyScript | 自带 SSE 重连、类型化异常 | 需额外跑 comfy-api-proxy；幂等键语义是"复用即拒绝 422" | 🔶 备选 |

**选定：④（模板化构建）+ ①（HTTP 闭环），② 只做环境初始化，③ 留作换 Agent 时的适配层。**

---

## 4. 最小可用闭环

```python
import json, uuid, time, urllib.request, urllib.parse, websocket

HOST = "127.0.0.1:8188"
CLIENT_ID = str(uuid.uuid4())

def submit(api_graph, timeout=20):
    pid = str(uuid.uuid4())                       # 客户端预生成 prompt_id，便于对账/去重
    body = json.dumps({"prompt": api_graph, "client_id": CLIENT_ID,
                       "prompt_id": pid}).encode()
    r = urllib.request.urlopen(f"http://{HOST}/prompt", body, timeout=timeout)
    return json.loads(r.read())                   # 400 + node_errors = 不可重试

def wait_done(ws, pid, hard_timeout=1800, idle_timeout=300):
    """双超时：总时长 + 无进度静默时长"""
    deadline, last = time.time() + hard_timeout, time.time()
    while True:
        ws.settimeout(30)
        try:
            out = ws.recv()
        except Exception:
            if time.time() > deadline or time.time() - last > idle_timeout:
                raise TimeoutError(pid)
            continue
        if not isinstance(out, str):
            continue                              # 二进制预览帧
        msg = json.loads(out)
        if msg["type"] == "executing":
            last = time.time()
            d = msg["data"]
            if d["prompt_id"] == pid and d["node"] is None:
                return                            # 完成
        elif msg["type"] == "progress":
            last = time.time()

def fetch(pid):
    h = json.loads(urllib.request.urlopen(
        f"http://{HOST}/history/{pid}", timeout=20).read())[pid]
    files = []
    for node_out in h["outputs"].values():
        for key in ("images", "gifs", "videos"):
            for f in node_out.get(key, []):
                q = urllib.parse.urlencode({"filename": f["filename"],
                                            "subfolder": f["subfolder"],
                                            "type": f["type"]})
                files.append((f["filename"],
                    urllib.request.urlopen(f"http://{HOST}/view?{q}").read()))
    return files

def free_vram():
    urllib.request.urlopen(urllib.request.Request(
        f"http://{HOST}/free",
        data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
        headers={"Content-Type": "application/json"}))

def run_one(api_graph, retries=2):
    ws = websocket.WebSocket()
    ws.connect(f"ws://{HOST}/ws?clientId={CLIENT_ID}")
    try:
        for attempt in range(retries + 1):
            pid = submit(api_graph)["prompt_id"]
            try:
                wait_done(ws, pid)
                return pid, fetch(pid)
            except TimeoutError:
                urllib.request.urlopen(urllib.request.Request(
                    f"http://{HOST}/interrupt", data=b"{}",
                    headers={"Content-Type": "application/json"}))
                free_vram()
                if attempt == retries:
                    raise
    finally:
        ws.close()
```

**要点：**
1. **客户端预生成 `prompt_id`** → 便于对账、去重、断点续跑
2. **双超时**：总时长 + 静默时长（ComfyUI 卡死只能杀进程，静默检测是唯一手段）
3. 超时先 `/interrupt` 再 `/free`，不要直接重启
4. **区分两类失败**：提交即 400（图校验失败，**不可重试**）vs 执行超时（**可重试**）

---

## 5. 模板化：Agent 只改这几个槽

官方示例的做法就是直接改节点输入：

```python
prompt["3"]["inputs"]["seed"] = 5
```

本项目进一步封装成槽位（见 `comfy/build_workflow.py`）：

| 槽位 | 对应节点 | 说明 |
|---|---|---|
| `MODEL` | `UNETLoader` / `MiniMaxH3Director` | 权重文件名，按档位选 |
| `MODE` | `MiniMaxH3Director.mode` | `t2va`/`i2va`/`l2va`/`fl2va`/`ref2va` —— **一个字符串切模式** |
| `PROMPT` | Director 的 prompt 输入 | H3 三段/六段式文本 |
| `REF_IMAGES` | Director 的图像槽 | 1–9 张 |
| `STEPS` | `BasicScheduler` | 4 / 8 / 20 |
| `SHIFT` | `MiniMaxH3SigmaShift` | 12 / 3 |
| `RES` | `Resolution Selector` | 按档位 |
| `SEED` | `DaSiWa_SeedControl` | 完整 64-bit |
| `SPARSE` | `Model Sparse Attention` 或 `Veda Sparse Attention (MiniMax H3)` | **互斥，构建期二选一** |
| `TURBO_LORA` | `LoraLoaderModelOnly` | 仅 `turbo=lora` 时发射该节点 |

---

## 6. 无人值守批量生产的九条规则

1. **LLM 不进每视频循环。** Agent 产出参数清单（JSONL），worker 消费。
2. **队列深度 1–3。** ComfyUI 单进程串行，塞满队列会让超时判断失真。用 `/queue` 观察。
3. **显存主动清。** 每个 job 结束 `POST /free {"unload_models":true,"free_memory":true}`；每 N 个 job 强制清一次。
   `--disable-smart-memory` **不要常开**（会变慢），只在 OOM 频繁时开。
4. **卡死检测用"最后 WS 事件时间戳"。** 建议静默阈值 300s；连续 M 次超时 → 杀 ComfyUI 子进程重启（用 supervisor 托管）。
5. **重试分级：**
   - 提交即 400 + `node_errors`（节点缺失/图校验失败）→ 立即失败并告警，**不重试**
   - OOM / 超时 / 队列满 → 降级重试（降分辨率 → 降帧数 → 换 `--lowvram`）
6. **断点续跑。** 任务表落 SQLite，状态机 `pending/running/done/failed`；启动时把 `running` 转回 `pending`。
7. **归档命名自己控制。** `filename_prefix = {job_id}_{shot_id}`，产物按 `out/{job_id}/` 归档。
   **不要依赖 ComfyUI 自动编号**（会重复、难对账）。
8. **可观测性。** 每个 job 记录 `prompt_id + client_id + workflow hash + seed + 耗时 + 峰值 VRAM`（`/system_stats` 采样）+ WS 事件 JSONL。失败时把当时的 API JSON 一并落盘，保证可复现。
9. **参考图先上传。** `POST /upload/image`（multipart），拿到 name 后填进节点输入。

---

## 7. 环境初始化（一次性，交给 comfy-cli）

```bash
comfy setup -y
comfy install --fast-deps
comfy node install <registry-id>        # id 必须小写
comfy node install-deps --workflow=workflows/h3_sla_fused.json
comfy node save-snapshot                # 环境快照，可复现
comfy launch --background -- --listen 127.0.0.1 --disable-auto-launch
```

- 全部命令支持 `--json` 结构化输出
- `comfy update all --exit-on-fail` 才会在节点更新失败时非 0 退出
- `export COMFY_LOCAL_URL=http://127.0.0.1:8189` 可把命令指向外部已启动实例

⚠️ **无头装节点的闸门**：ComfyUI-Manager 的 `POST /customnode/install/git_url` 受
`config.ini` 的 `allow_git_url_install` / `allow_pip_install` 控制，**默认 false，且只在 loopback 生效**。
自动化部署前必须先改配置再重启。

---

## 8. 换 Agent 需要动什么

**只动 L4。** L1–L3 完全不变。

给新 Agent 三样东西即可：
1. `agent/TOOL-CONTRACT.md` —— 15 个工具的签名与语义
2. `agent/SKILL.md` —— 执行手册
3. 任意一个适配器：MCP server（Hermes/OpenClaw/Claude 都支持）/ CLI / OpenAPI

Comfy-Org 官方已有 **`comfy-mcp`**（stdio、40 tools、基于 comfy-cli、要求 comfy-cli>=1.14.0、
AGPL-3.0-or-Commercial），核心链路 `server_info → run_workflow(wait=False) → fetch_outputs(prompt_id, out_dir)`。
但 stdio 长任务会阻塞，建议本项目自建 HTTP MCP，**不要**直接依赖它跑长任务。
