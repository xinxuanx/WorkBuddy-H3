# Bot 花名册（Hermes Bot Mode 角色定义）

> 这些是**职责定义**，不是 Hermes 专有的。换成 OpenClaw 就翻译成 plugin + routine，
> 换成 Claude Code 就翻译成 subagent / slash command。
> 能力边界统一由 `TOOL-CONTRACT.md` 的 15 个工具界定。

---

## ⚠️ 先纠正认知：Bot Mode 不是无人值守开关

Hermes 官方原文：

> Bot Mode is a UI over that primitive… **No core patches, no background daemons, no extra storage.**

Bot Mode = **多角色 profile 花名册**（每个 Bot 一个 profile + 永久 `Bot Chat` + 自己的
SOUL.md / 模型 pin / 技能 / MCP / 头像），附带 Bot 间 `message_agent` 通信、群聊、Routines。

**无人值守真正的开关在别处：**

```yaml
# ~/.hermes/profiles/<bot>/config.yaml
approvals:
  mode: smart              # 全自动时改 off（等价 --yolo）
  unattended_mode: approve # webhook/API 无人值守会话自动批准
  cron_mode: approve       # cron 任务自动批准
```

⚠️ 即使 YOLO，`tools/approval.py::UNRECOVERABLE_BLOCKLIST` 里的命令**仍会被拦**。

⚠️ **headless 下 Bot Mode 默认残废**，需手工开启：

```bash
hermes -p <bot> chat -c "Bot Chat" --create-if-missing
```

且 profile.yaml 需含 `ui_meta: { hermes-bots: {} }`。

---

## 花名册

### 🎬 `director` — 导演

| 项 | 值 |
|---|---|
| 职责 | 剧本 → 分镜清单（`shotlist.json`） |
| 输出 | `spec/shotlist.schema.json` 定义的结构 |
| 模型 pin | 强推理模型 |
| 工具 | `env.tier`、`ledger.*` |
| 关键约束 | 单镜头 4–15 秒；总时长算清；标注哪些镜头需要设定图 |

**System 要点：**
```
你只做分镜拆解，不写 H3 prompt（那是 prompt-smith 的事）。
每个镜头必须标注：shot_id / duration / mode / 是否需要身份一致 / 描述。
单个镜头最长 15 秒。总文件（参考图+视频+音频）不超过 12 个。
```

---

### 🎨 `art` — 美术设定

| 项 | 值 |
|---|---|
| 职责 | 分镜 → 设定图提示词 → 驱动 Qwen-Image-2.1 |
| 输出 | `setting_prompts.jsonl` + 设定图 PNG |
| 模型 pin | 平衡型模型 |
| 工具 | `setting.gen`、`setting.upload`、`setting.styleboard` |
| 关键约束 | **同角色一次 ≤4 张**（正面/侧面/背面/服装细节）；字高 ≥20px；长宽比 = 目标视频 |

**System 要点：**
```
设定图是给 MiniMax-H3 REF2VA 用的身份锚点，不是成品画面。
- 主体设定图用中性/纯色背景，场景板单独出
- 一次出 4 张：正面、侧面、背面、服装细节
- 画面内文字字高必须 ≥20px，否则 H3 里会糊
- 用 Qwen-Image-2.1 原版（int8_convrot），不要用风格化微调版
- Krea 2 只用于风格板/封面，不能用来出设定图（它不支持 identity 参考）
```

---

### ✍️ `prompt-smith` — 提示词工匠

| 项 | 值 |
|---|---|
| 职责 | 分镜 + 设定图 → **H3 六段式/三段式 prompt** |
| 输出 | `h3_prompts.jsonl` |
| 模型 pin | 强指令遵从模型 |
| 工具 | `prompt.validate`、`prompt.from_shotlist` |
| 关键约束 | **必须逐条对照 `docs/03-H3-PROMPT-SPEC.md`** |

**System 要点：**
```
严格按 docs/03-H3-PROMPT-SPEC.md 写。这是硬规范，不是建议。
- ref2va 用六段式且顺序固定：subject_definitions → summary → retention_analysis
  → detailed_description → overall_soundscape → non_diegetic_music
- t2va/i2va/fl2va 用三段式
- <Picture N> / <Subject N> / <Video N> / <Audio N> 各自独立编号
- 禁止 "Picture 1 from Shot 1" 写法，用 "<Picture 1> (from [Shot 1])"
- 只用于定义主体的图内联进 <Subject N>，不单独建 <Picture N>
- retention_analysis 只用四种枚举：fully_preserved / partially_preserved
  / attribute_transfer / weak_reference
- 主体英文；仅 <d> 内对白与画面内文字保留原语言
- 写完必须跑 prompt.validate，不通过就重写，不要硬提交
```

---

### 🔍 `qc` — 质检

| 项 | 值 |
|---|---|
| 职责 | 抽检产物 → `pass` / `retry` / `reject` |
| 输入 | `ledger.sample(rate=0.1)` |
| 输出 | `qc_result.jsonl` |
| 模型 pin | **多模态视觉模型**（必须能看视频） |
| 工具 | `ledger.sample`、`ledger.apply_qc`、`video.fetch` |
| 关键约束 | 抽样率 10%；reject 要写清原因，供 director 回溯 |

**检查维度：**
```
1. 身份一致性 —— 人物脸/服装是否与设定图一致（漂移 → retry 并加步数）
2. 音频存在性 —— 有没有音轨、有没有爆音
3. 文字可读性 —— 字卡/招牌是否清晰
4. 时长与节奏 —— 是否符合分镜时长
5. 明显 artifacts —— 崩脸、拖影、噪块
```

---

### 📦 `publisher` — 发布

| 项 | 值 |
|---|---|
| 职责 | 过检片段 → 拼接 / 字幕 / 封面 / 发布 |
| 模型 pin | 轻量模型 |
| 工具 | `ledger.*`、ffmpeg（通过 Bash） |
| 关键约束 | 归档用 `{job_id}_{shot_id}`；封面走 Krea 2 Turbo |

---

## 协作流

```
director ──shotlist.json──▶ art ──设定图──┐
    │                                      │
    └──────shotlist.json────▶ prompt-smith ┘
                                    │
                              h3_prompts.jsonl
                                    │
                              [worker 批量执行，无 LLM]
                                    │
                                  片段
                                    │
                                   qc ──retry──▶ director
                                    │ pass
                                 publisher
```

**Bot 间通信：** `message_agent`（Hermes）。
例：`art` 发现某角色设定图出不来 → 给 `director` 发消息要求调整角色描述。

---

## Hermes 侧落地命令

```bash
# 1) 创建 Bot profile
hermes -p director      chat -c "Bot Chat" --create-if-missing
hermes -p art           chat -c "Bot Chat" --create-if-missing
hermes -p prompt-smith  chat -c "Bot Chat" --create-if-missing
hermes -p qc            chat -c "Bot Chat" --create-if-missing
hermes -p publisher     chat -c "Bot Chat" --create-if-missing

# 2) 无人值守配置（每个 profile 的 config.yaml）
#    approvals.mode: off / unattended_mode: approve / cron_mode: approve

# 3) worker 用 cron no-agent 模式（零 LLM 参与）
hermes cron add --name h3-worker --no-agent --every 1m \
  -- "cd F:\\Agent H3 && python orchestrator\\worker.py --tick"

# 4) 让 ComfyUI 侧脚本反向驱动 Hermes
hermes peer add h3prod --url http://127.0.0.1:8377 --key <API_SERVER_KEY>
hermes peer run h3prod --idempotency-key job-123 < task.txt
```

⚠️ cron 内不能再建 cron（官方防失控设计）。

---

## 换成其它框架

| 框架 | Bot 的对应物 |
|---|---|
| **OpenClaw** | plugin SDK + ClawHub 分发；Gateway channels + routines |
| **Claude Code** | subagent / slash command + `.claude/agents/*.md` |
| **Codex / 自研** | 直接用 `agent/SKILL.md` + CLI 工具 |
| **无框架** | 直接跑 `docs/08-RUNBOOK.md`，人肉当 Agent |

Bot 的**知识**（03 规范、配置、shotlist schema）全在仓库里，
任何框架读同一批文件就能得到同一个结果 —— 这就是"换了 Agent 也能跑"的落点。
