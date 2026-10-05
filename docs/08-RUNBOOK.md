# 08 — 执行手册：从零到出片

> 照着跑一遍。每一步都可验证，卡住就看「失败排查」。

---

## 阶段 0：准备（一次性，约 1–2 小时）

### 0.1 安装 ComfyUI

```bash
# 解压 F:\ComfyUI-portable-nvidia.7z 到 F:\ComfyUI
# 确认版本 >= 0.38.0
python -c "import sys; sys.path.insert(0,r'F:\ComfyUI'); import comfyui_version as v; print(v.__version__)"
```

**验证点：** 输出 >= 0.38.0

### 0.2 装节点

```bash
comfy setup -y
comfy node install comfyui-kjnodes
comfy node install comfyui-gguf
comfy node install dasiwa-nodes
comfy node install veda-sparse-attention      # 仅走 Veda 链路时
git clone https://github.com/sepiablue-ai/ComfyUI-H3-X2-Stream   custom_nodes/ComfyUI-H3-X2-Stream
git clone https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context custom_nodes/ComfyUI-H3-Motion-Context
git clone https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes    custom_nodes/ComfyUI-DaSiWa-Nodes
pip install sageattention websocket-client pyyaml
```

> ⚠️ 若走 HTTP API 装 git 节点，必须先改 `config.ini`：
> `allow_git_url_install = true`、`allow_pip_install = true`，然后重启 ComfyUI。
> 默认 false 且只在 loopback 生效。

**验证点：** `comfy node show installed` 里能看到上述节点

### 0.3 放模型

按 [docs/02-MODEL-SELECTION.md §5](02-MODEL-SELECTION.md) 的目录树放。
**最低可启动组合（10GB 档位）：**

```
models/diffusion_models/MiniMaxH3/dasiwa_minimax_h3_ref2va_v3_pruned_hybrid_turbo_int4.safetensors  (12.25GB)
models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors                                   (15.7GB)
models/vae/minimax_h3_lynnreal_light_vae_int8_convrot.safetensors                                    (2.14GB)
models/vae/minimax_h3_audio_vae_fp32.safetensors                                                     (0.6GB)
```

**验证点：** `GET /models/diffusion_models` 能列出

### 0.4 启动

```bash
comfy launch -- --listen 127.0.0.1 --port 8188 \
  --lowvram --reserve-vram 0.6 --async-offload 2 \
  --fast fp16_accumulation --disable-auto-launch
```

**验证点：** `curl http://127.0.0.1:8188/system_stats` 返回 JSON

### 0.5 保存环境快照

```bash
comfy node save-snapshot
```

---

## 阶段 1：单镜头打通（先跑通一个，别上来就批量）

### 1.1 构建工作流

```bash
cd "F:\Agent H3"
python comfy/build_workflow.py \
  --tier t10 \
  --weight dasiwa_hybrid_turbo_v3_int4 \
  --attention sla \
  --turbo fused \
  --mode t2va \
  --out workflows/
```

**验证点：** `workflows/h3_sla_fused_t2va.json` 生成成功

### 1.2 填参数并提交

```bash
python orchestrator/worker.py --once \
  --workflow workflows/h3_sla_fused_t2va.json \
  --set PROMPT="integrated_multimodal_description: [Shot 1] A lone astronaut floats above a neon-lit cyberpunk cityscape at night.
overall_soundscape: Distant rain on metal, faint city hum.
non_diegetic_music: Pulsing dark synthwave beat enters at 00:02.000." \
  --set SEED=42 --set STEPS=4
```

**验证点：** 产出 `out/<job_id>/` 下有 mp4，且有音频轨

### 1.3 基线计时

记录耗时。若 > 10 分钟，检查：
- 权重是否选了 int8 而不是 int4/w4a8
- 步数是否 > 4
- 分辨率是否超过 544×960

---

## 阶段 2：设定图链路

### 2.1 出设定图

```bash
python orchestrator/worker.py --once \
  --workflow workflows/qwen21_setting.json \
  --set PROMPT="<Subject 1> is a young woman with short dark hair, wearing a linen coat, standing in a sunlit garden. Neutral grey background, full body, front view." \
  --set RES="1088x1920" --set STEPS=25 --set SEED=1001
```

**要点：**
- 同角色出 **正面 / 侧面 / 背面 / 服装细节** 四张，≤ 4 张一批（10GB 卡可开 KV cache）
- 字卡文字 **字高 ≥ 20px** 才稳定
- 设定图长宽比 = 目标视频长宽比

### 2.2 设定图 → REF2VA

```bash
python orchestrator/worker.py --once \
  --workflow workflows/h3_sla_fused_ref2va.json \
  --set REF_IMAGES="charA_front.png,charA_side.png,charA_back.png,charA_costume.png" \
  --set PROMPT_FILE=spec/samples/ref2va_sample.txt \
  --set STEPS=8        # ⚠️ 强身份一致时禁止 4 步
  --set SEED=2001
```

**验证点：** 出片里人物的脸/服装与设定图一致

---

## 阶段 3：批量生产

### 3.1 Agent 产出任务清单

```bash
# 让 Agent（任意框架）按 agent/TOOL-CONTRACT.md 产出 shots.jsonl
# 每行一个 job：{job_id, mode, prompt, ref_images, seed, steps, res, variant}
```

### 3.2 入账本

```bash
python orchestrator/job_ledger.py import shots.jsonl
python orchestrator/job_ledger.py stats
```

### 3.3 常驻消费

```bash
python orchestrator/worker.py --loop --concurrency 1
```

或交给系统定时器（Hermes cron no-agent 模式）：

```bash
hermes cron add --name h3-worker --no-agent --every 1m -- "cd /d F:\Agent H3 && python orchestrator\worker.py --tick"
```

### 3.4 断点续跑

```bash
python orchestrator/job_ledger.py reset-stale      # running → pending
python orchestrator/worker.py --loop
```

---

## 阶段 4：抽检与发布

```bash
python orchestrator/job_ledger.py sample --rate 0.1 --out qc_batch.jsonl
# Agent(qc bot) 视觉审查 → 标记 pass / retry / reject
python orchestrator/job_ledger.py apply-qc qc_result.jsonl
```

---

## 失败排查

| 现象 | 原因 | 处置 |
|---|---|---|
| `/prompt` 返回 400 + `node_errors` | 节点缺失或图校验失败 | **不可重试**，检查节点是否装全 |
| 提交成功但一直无进度 | ComfyUI 卡死 | 静默 300s 触发 → `/interrupt` → `/free` → 连续多次则重启进程 |
| OOM | 权重/分辨率过大 | 降分辨率 → 降帧数 → 加 `H3 Chunk FeedForward chunks=4` → 换 `--novram` |
| 出片没有音频 | 缺音频 VAE 或走了非 REF2VA | **REF2VA 必需 `minimax_h3_audio_vae_fp32`**；确认 shift_audio = 3 |
| 人物脸漂移 | 4 步 turbo + ref2va | ⚠️ **官方已知问题**，强身份一致时禁用 4 步 |
| Veda 没生效 | 同时挂了原生 `Model Sparse Attention` | **互斥**，构建期二选一 |
| 装节点静默失败 | `config.ini` 的 install 开关默认 false | 改配置 + 重启 |
| 生成极慢（>10min/片） | 10GB 卡用了 int8 + 高步数 | 换 int4/w4a8 + 4 步 + 544×960 |
| 中文文字糊 | 字高 < 20px | 提到 ≥20px；或正片设定图回退到 25–40 步原版（别用 Viggle 5 步） |
| 首尾帧锚点丢了 | Motion Context 会丢弃 `first_frame` | 已知行为，`last_frame` 保留 |

---

## 上线前检查清单

- [ ] ComfyUI >= 0.38.0
- [ ] 权重放在 `models/diffusion_models/MiniMaxH3/`（不是根目录）
- [ ] 音频 VAE 已放（REF2VA 必需）
- [ ] 启动参数带 `--lowvram --async-offload 2`
- [ ] `config/registry.yaml` 的 `comfy_root` 指向真实路径
- [ ] `sink_conditioning = exact_kv_and_rows`
- [ ] Veda 与 SLA **没有**同时出现在同一张图里
- [ ] `mode=ref2va` + 强身份一致 → 步数 ≠ 4
- [ ] 归档命名用 `{job_id}_{shot_id}`，不依赖 ComfyUI 自动编号
- [ ] 环境快照已保存（`comfy node save-snapshot`）
- [ ] 商用场景已确认 Qwen-Image-2.1 授权状态
