---
name: workbuddy-h3
description: >
  Agent + ComfyUI 全自动短视频生产线。当你需要产出 MiniMax-H3 短视频、
  生成设定图、构建 ComfyUI 工作流、或批量跑视频任务时使用本技能。
  主模型 MiniMax-H3，设定图 Qwen-Image-2.1，风格板 Krea 2。
---

# WorkBuddy H3 — Agent 执行手册

> 你是一个执行者，不是创造者。**所有规范都在仓库里，照着读，别自己发明。**

---

## 0. 开工前必须读的文件

1. `config/registry.yaml` —— 硬件档位与模型注册表（**唯一配置源**）
2. **`spec/official/h3-prompt-writing/references/base-en.txt`** —— 官方权威规范（T2VA/I2VA/FL2VA/**L2VA**）
3. **`spec/official/h3-prompt-writing/references/ref-en.txt`** —— 官方权威规范（Ref2VA 全参考）
4. `docs/03-H3-PROMPT-SPEC.md` —— 上面两份的中文索引与工程补充
5. `agent/TOOL-CONTRACT.md` —— 你能调的 15 个工具

> 前两份是 MiniMax 官方从 `github.com/MiniMax-AI/MiniMax-H3` 的 `.agents/skills/` 原样 vendored 的，
> **冲突时以它们为准**。官方技能自带 `SKILL.md`，可直接安装到 Claude Code（`.claude/skills/`）
> 或任何兼容 `agentskills.io` 的 Agent —— frontmatter 明确写了"不绑定 OpenAI"。

读之前不要动手。

---

## 1. 你的工作边界

### ✅ 你负责（阶段边界，一次性）

| 阶段 | 产出 |
|---|---|
| 剧本 → 分镜 | `shotlist.json`（结构见 `spec/shotlist.schema.json`） |
| 分镜 → 设定图提示词 | `setting_prompts.jsonl` |
| 分镜 → H3 prompt | `h3_prompts.jsonl`（**严格按 03 规范**） |
| 抽检 | `qc_result.jsonl` |
| 打包发布 | 成片 |

### ❌ 你不负责（交给 worker，不要介入）

- 批量出设定图
- **批量生成视频** ★
- 队列管理、重试、显存清理

> **铁律：不要把 LLM 放进每视频的循环。**
> 你产出参数清单（JSONL），worker 消费。这是成本与确定性的关键。
> 一个 60 镜头的片子，你应该只跑 3–4 次 LLM 调用，不是 60 次。

---

## 2. 标准作业流程

```
Step 1  env.status() + env.tier()
        → 确认 ComfyUI 在线、拿到档位（t10/t16/t24/t48）

Step 2  剧本 → shotlist.json
        → 每个镜头：shot_id / duration / mode / 描述 / 是否需要设定图

Step 3  对需要身份一致的镜头：
        setting.gen(subject_prompt, count=4, res="1088x1920")
        → 同角色出 正面/侧面/背面/服装细节 四张
        → ⚠️ count ≤ 4（10GB 档位可开 KV cache）

Step 4  prompt.from_shotlist(shotlist.json, mode)
        → 生成 H3 prompt
        → ⚠️ 必须跑 prompt.validate()，不通过就重写，别硬提交

Step 5  workflow.build(variant, mode, weight, tier)
        → 得到 API JSON

Step 6  ledger.import(h3_prompts.jsonl)
        → 入账本

Step 7  通知启动 worker（你自己不要轮询）
        python orchestrator/worker.py --loop

Step 8  ledger.sample(rate=0.1) → 你做视觉抽检
        ledger.apply_qc(qc_result.jsonl)

Step 9  打包发布
```

---

## 3. 提示词写作：最重要的一节

### 选对结构

```
mode = ref2va  → 六段式，顺序固定：
   subject_definitions → summary → retention_analysis
   → detailed_description → overall_soundscape → non_diegetic_music

mode = t2va / i2va / fl2va / l2va → 指令行 + 三段式：
   {{指令行}}            ← 有参考图时必须有，且是第一行，后跟一个空行
   integrated_multimodal_description → overall_soundscape → non_diegetic_music
```

### 指令行逐字照抄（别改写）

```
T2VA    （无指令行）
I2VA    For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
FL2VA   How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
L2VA    How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

### 必死错误清单

```
❌ FL2VA 写成 <Picture 1> (from [Shot 1])   → ✅ FL2VA 裸写：Picture 1 (from Shot 1)
❌ 指令行放在字段之后 / 后面没空行           → ✅ 第一行 + 一个空行
❌ 漏掉 L2VA（尾帧模式）                    → ✅ L2VA = 反推前置状态 → 收敛到尾帧
❌ 音频用了 fully_preserved                 → ✅ 音频另有一套：fully_copy/partially_copy/reference/weak_reference
❌ summary 没有任务类型前缀                 → ✅ [reference generation] / [video editing] ...
❌ retention_analysis 里写 (S1)             → ✅ 该段不写 (Sx)
❌ 画外音没声明嘴唇闭合                     → ✅ while his lips remain completely closed
❌ 运镜在句末堆标签                         → ✅ 写成句子里的自然英文（类型+幅度+速度）
❌ 画面内文字没加双引号                     → ✅ 英文双引号包裹，保留原语言
❌ 角色能听到的音乐写进 non_diegetic_music   → ✅ 那是 diegetic，写进主描述段
❌ overall_soundscape 随便写 N/A            → ✅ 仅明确全片静音时才用
❌ 单独为"定义人物的图"建 <Picture N>        → ✅ 内联进 <Subject N>
❌ 主体写中文                               → ✅ 主体英文，仅 <d> 与画面内文字保留原语言
❌ [Shot 1] 带时间戳                        → ✅ 首镜不带，后续 [Shot N] At MM:SS.mmm
❌ 参考图 10 张                             → ✅ ≤ 9
❌ ref2va 强身份一致却用 4 步                → ✅ ≥ 8 步（官方已知漂移问题）
```

### 提交前自检（跑 `prompt.validate`）

- [ ] 模式与段落结构匹配？
- [ ] 有参考图 → 指令行是第一行且后跟空行？字面写法与模式一致（FL2VA 无尖括号）？
- [ ] `<Picture N>` / `<Subject N>` / `<Video N>` / `<Audio N>` 各自独立从 1 连续编号？
- [ ] `retention_analysis` 可见内容 4 种、音频 4 种，没混用？
- [ ] `summary` 有方括号任务类型前缀？
- [ ] 参考资产：图 ≤9、视频 ≤3、音频 ≤3、总 ≤12、单段 2–15s、总 ≤15s？
- [ ] 对白 `<d>` 包裹、说话人 `(S1)`，跨镜一致？
- [ ] 画外音 + 嘴唇闭合？
- [ ] 运镜写成自然英文句子？
- [ ] mode=ref2va 且强身份 → 步数 ≠ 4？

---

## 4. 常见任务的参数速查

| 任务 | variant | mode | 步数 | 说明 |
|---|---|---|---|---|
| 常规镜头 | `h3_sla_fused` | `t2va`/`i2va` | 4 | 默认 |
| 带设定图的镜头 | `h3_sla_fused` | `ref2va` | **8**（不是 4） | 强身份一致禁 4 步 |
| 首尾帧镜头 | `h3_sla_fused` | `fl2va` | 4 | 2 张图 |
| Hero shot / 特写 | `h3_sla_none` 或 `h3_sla_lora` | 任意 | 20 / 8 | 换 Singularity w4a8 权重 |
| 极致速度（ComfyUI≥0.38） | `h3_veda_fused` | 任意 | 4 | **不能与 SLA 同时挂** |
| A/B 对照 | `h3_dense_*` | 任意 | 20 | 建质量基线 |

采样参数（除步数外基本固定）：

```
sampler: res_multistep
scheduler: simple
shift_video: 12
shift_audio: 3
CFG: 无（走 BasicGuider，别硬塞 CFG 节点）
denoise: 1.0
sink_conditioning: exact_kv_and_rows   ← 稀疏注意力，保住 reference rows 与音频
```

---

## 5. 你会踩的坑

| 坑 | 处置 |
|---|---|
| Veda 与 SLA 同时挂 → Veda 永不生效 | **互斥**，一个图里只能有一个 |
| 想试着跑 20 步 | 10GB 卡上 20 步 × int8 = 420GB 搬运，几十分钟一片。**4 步 + int4** |
| 出片没声音 | 缺 `minimax_h3_audio_vae_fp32`（REF2VA 必需）+ `shift_audio=3` |
| 中文文字糊 | 字高 < 20px。提到 ≥20px |
| 装节点静默失败 | `config.ini` 的 `allow_git_url_install`/`allow_pip_install` 默认 false |
| 人物脸漂移 | 4 步 turbo + ref2va 的已知问题，加步数 |
| 依赖 ComfyUI 自动编号归档 | 会重复、难对账。用 `{job_id}_{shot_id}` |
| 提交即 400 | 节点缺失/图校验失败，**不要重试**，去查环境 |

---

## 6. 你不需要知道的事

这些已经固化在配置与代码里，不要自己调：

- 权重文件选哪个（在 `config/registry.yaml`）
- 分辨率（按档位自动给）
- 稀疏注意力参数（模板里给好）
- VAE 选哪个（档位决定）
- 队列深度、重试策略、超时阈值（worker 管）

**你只管：剧本 / 分镜 / 提示词 / 抽检 / 打包。**

---

## 7. 一句话总结

> 读规范 → 出清单 → 交给 worker → 抽检 → 打包。
> **不要自己去跑每一个视频。**
