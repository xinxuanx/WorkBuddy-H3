# 工具契约（Tool Contract）

> **换 Agent 框架时，唯一需要重新实现的就是这 15 个工具。**
> L1–L3（ComfyUI、适配层、Orchestrator）完全不变。
> 实现方式任选：MCP server / CLI / OpenAPI HTTP / 直接 Python import。

---

## 0. 通用约定

- 所有工具返回 JSON：`{"ok": true, "data": {...}}` 或 `{"ok": false, "error": {"code": "...", "msg": "..."}}`
- 错误码：`INVALID_ARGS` / `NOT_FOUND` / `VALIDATION_FAILED` / `COMFY_DOWN` / `TIMEOUT` / `OOM`
- 所有路径用正斜杠，相对路径相对 `comfy_root`
- `job_id` 由调用方生成并贯穿全流程（幂等）

---

## 1. 环境类

### `env.status()`
查 ComfyUI 是否在线、版本、显存。

```json
{"ok": true, "data": {
  "online": true,
  "comfyui_version": "0.38.0",
  "gpu": "RTX 3080",
  "vram_total_gb": 10,
  "vram_free_gb": 9.2,
  "models": {"diffusion_models": ["..."], "vae": ["..."]}
}}
```

### `env.tier()`
返回当前硬件档位与可用权重/分辨率/步数。读 `config/registry.yaml`。

### `env.nodes()`
列出已安装自定义节点。用于判断某变体是否可用（如 Veda）。

---

## 2. 工作流类

### `workflow.build(variant, mode, weight, tier, **overrides) -> workflow_path`

从模板构建 API JSON。

| 参数 | 取值 |
|---|---|
| `variant` | `h3_{sla,veda,dense}_{fused,lora,none}` |
| `mode` | `t2va` / `i2va` / `l2va` / `fl2va` / `ref2va` |
| `weight` | `config/registry.yaml` 里 `h3_weights` 的键 |
| `tier` | `t10` / `t16` / `t24` / `t48` |
| `overrides` | `steps` / `seed` / `res` / `shift_video` / `shift_audio` |

**会触发硬校验**（见 docs/00 §5），校验失败返回 `VALIDATION_FAILED` 而不是产出坏图。

### `workflow.list_variants()`
返回 9 个变体的定义与适用说明。

---

## 3. 提示词类

### `prompt.validate(text, mode) -> {valid, errors[]}`

按 [docs/03-H3-PROMPT-SPEC.md](../docs/03-H3-PROMPT-SPEC.md) 校验：

| mode | 检查项 |
|---|---|
| `ref2va` | 六段式顺序、`<Picture N>`/`<Subject N>` 独立编号、`retention_analysis` 四种枚举、无 "Picture N from Shot M" 错误写法 |
| `t2va`/`i2va`/`fl2va` | 三段式、`[Shot 1]` 无时间戳、后续 `At 00:0X.XXX` |
| 通用 | 主体英文、对白在 `<d>` 内、说话人 `(S1)(S2)`、参考资产数量限额 |

### `prompt.from_shotlist(shotlist_path, mode) -> prompt_jsonl`
把分镜清单转成 H3 prompt 列表（按模式套用三段/六段式骨架）。

> 这是 `prompt-smith` Bot 的主要工具。**骨架在 `spec/prompt_recipe.md`，不在 Agent 脑子里。**

---

## 4. 设定图类

### `setting.gen(subject_prompt, count, res, seed) -> job_id`
用 Qwen-Image-2.1 出设定图。

- `count` ≤ 4（10GB 档位可开 KV cache；超过会走 `use_kv_cache=False` 慢路径）
- 默认 `res = 1088x1920`（9:16）
- 默认 25 步 / cfg 1 / euler / simple

### `setting.styleboard(style_prompt, res, seed) -> job_id`
用 Krea 2 Turbo 出风格板/封面。8 步 / CFG 0。

### `setting.upload(path) -> name`
上传参考图到 ComfyUI（`POST /upload/image`）。

---

## 5. 视频生成类

### `video.submit(workflow_path, job_id, prompt, ref_images[], seed, **params) -> prompt_id`
提交单个生成任务。返回 `prompt_id` 用于追踪。

### `video.wait(prompt_id, hard_timeout, idle_timeout) -> status`
WebSocket 监听，双超时。

### `video.fetch(prompt_id) -> [file_paths]`
从 `/history` + `/view` 取回产物，按 `{job_id}_{shot_id}` 归档到 `out/{job_id}/`。

### `video.run(workflow_path, job_id, ...) -> {prompt_id, files}` ⭐
上面三步的组合（最常用）。含重试分级：

| 失败类型 | 处置 |
|---|---|
| 提交即 400（`node_errors`） | **不重试**，返回 `VALIDATION_FAILED` |
| OOM | 降分辨率 → 降帧数 → 换 `--lowvram` |
| 超时 | `/interrupt` → `/free` → 重试 |

---

## 6. 账本类

### `ledger.import(jsonl_path)`
导入任务清单。

### `ledger.stats() -> {pending, running, done, failed}`

### `ledger.sample(rate) -> jsonl_path`
按比例抽样供 QC。

### `ledger.apply_qc(result_jsonl)`
应用 `pass` / `retry` / `reject` 结果。

### `ledger.reset_stale()`
把 `running` 转回 `pending`（断点续跑）。

---

## 7. 工具清单汇总

| # | 工具 | 类别 |
|---|---|---|
| 1 | `env.status` | 环境 |
| 2 | `env.tier` | 环境 |
| 3 | `env.nodes` | 环境 |
| 4 | `workflow.build` | 工作流 |
| 5 | `workflow.list_variants` | 工作流 |
| 6 | `prompt.validate` | 提示词 |
| 7 | `prompt.from_shotlist` | 提示词 |
| 8 | `setting.gen` | 设定图 |
| 9 | `setting.styleboard` | 设定图 |
| 10 | `setting.upload` | 设定图 |
| 11 | `video.submit` | 视频 |
| 12 | `video.wait` | 视频 |
| 13 | `video.fetch` | 视频 |
| 14 | `video.run` ⭐ | 视频 |
| 15 | `ledger.*`（5 个子命令） | 账本 |

---

## 8. 最小实现示例（任意框架）

**CLI（最简单，任何能跑 shell 的 Agent 都能用）：**

```bash
python -m agent.cli env.status
python -m agent.cli workflow.build --variant h3_sla_fused --mode ref2va --tier t10
python -m agent.cli prompt.validate --mode ref2va --file p.txt
python -m agent.cli video.run --workflow w.json --job-id j001 --prompt-file p.txt
```

**MCP server（Hermes / OpenClaw / Claude 都支持）：**
把上面 15 个工具注册成 MCP tools 即可。建议走 **HTTP** 而非 stdio，
因为长任务会阻塞 stdio。

**直接 Python（Claude Code / Codex 这类有执行环境的）：**

```python
from agent.api import video
video.run(workflow_path="workflows/h3_sla_fused_ref2va.json",
          job_id="j001", prompt=open("p.txt").read(),
          ref_images=["charA_front.png"], seed=2001)
```

---

## 9. 换 Agent 的 checklist

- [ ] 让新 Agent 读 `agent/SKILL.md`
- [ ] 实现或接入这 15 个工具（CLI 最快）
- [ ] 确认它能读 `config/registry.yaml`（选档位/权重）
- [ ] 确认它写提示词前会跑 `prompt.validate`
- [ ] 确认它知道"LLM 不进每视频循环"（批量走 `ledger.import` + worker）
- [ ] 跑一遍 [docs/08-RUNBOOK.md](../docs/08-RUNBOOK.md) 阶段 1 验证
