# 05 — Agent 框架与 Hermes Bot Mode 的真实作用

> 这一章有一个**必须纠正的认知**：Bot Mode 不是无人值守开关。

---

## 1. OpenClaw 是什么

`github.com/openclaw/openclaw` **就是** Clawdbot → Moltbot → OpenClaw 那一支（仓库改名迁移，
`clawdbot/clawdbot` 会 301 到 `openclaw/openclaw`）。作者 Peter Steinberger，现由 OpenClaw Foundation
（501(c)(3)）托管，391k stars，MIT，TypeScript/Node pnpm monorepo。

**架构：** 核心是 **Gateway（本地控制平面）**，管理 sessions / tools / events / channels；
上接 20+ 聊天渠道（Discord/Slack/Telegram/WhatsApp/iMessage/Signal…），下接可插拔 model providers
与 agent harness。三种操作面：Control UI / CLI / TUI。扩展走 plugin SDK，生态分发在 ClawHub。
架构原则原文：**"trusted gateway, untrusted execution, deterministic policy"**。

> ⚠️ **OpenClaw 没有 "bot mode" 这个术语** —— README 与文档站均无。
> 最接近的是 Channels + daemon 化 Gateway 常驻，但官方不叫 bot mode。

⚠️ 旁证：`hermes-agent` 提供 `hermes claw migrate` 从 OpenClaw 迁移数据
（SOUL.md / MEMORY.md / USER.md / skills / API keys），说明 **OpenClaw 与 Hermes 是两个独立项目**。

---

## 2. Hermes Agent 的 Bot Mode —— 真相

官方 `bot-mode.md` 开篇原文：

> **Bot Mode** turns your Hermes profiles into a roster of named **Bots**. Each Bot has its own
> role, model, memory, skills, and avatar; Bots run recurring routines, deliberate together in
> group chats, and message each other directly.

关键原文（**打消"后台常驻/自动批准"的想象**）：

> There is no new primitive to learn: a Bot **is** a Hermes profile — isolated config, memory,
> skills, credentials, and chat history under `~/.hermes/profiles/<name>/`. Bot Mode is a UI over
> that primitive… **No core patches, no background daemons, no extra storage.**

> Bot Mode ships **built into the desktop app** and is **on by default**.

### 所以 Bot Mode 到底是什么

**= 桌面端 UI 层的"多角色 Bot 花名册"。** 每个 Bot = 一个 profile + 一个永久 `Bot Chat` +
自己的 SOUL.md / 模型 pin / 技能 / MCP / 头像。附带 Bot 间互发消息（`message_agent`）、群聊、
Routines（= cron）。

| 常见误解 | 事实 |
|---|---|
| ❌ bot mode 是无人值守开关 | ✅ 是**多角色 UI** |
| ❌ 有 `--bot` 参数 | ✅ 没有。CLI 等价物是 `hermes -p <bot> chat` |
| ❌ 开了就自动批准工具调用 | ✅ 不。**要单独配 approvals，见 §3** |
| ❌ 有后台守护进程 | ✅ 官方明写 "no background daemons" |

### ⚠️ headless 下 Bot Mode 默认残废

官方明确：需要手工满足两个条件才启用 `message_agent`
1. 会话标题必须是 `Bot Chat`
2. 任一 profile 的 `profile.yaml` 含 `ui_meta: { hermes-bots: {} }`

> on a **headless install with no desktop app** (gateway plus Telegram, say) nothing ever writes
> either marker, so `message_agent` is unreachable…

手工开启：

```bash
hermes -p <bot> chat -c "Bot Chat" --create-if-missing
```

---

## 3. ★ "无人值守"真正的开关在别处

`security.md` 的 approvals 配置：

```yaml
approvals:
  mode: smart            # smart | off
  cron_mode: deny        # deny | approve — cron 任务遇到危险命令怎么办
  single_query_mode: deny  # deny | approve — 一次性 -q 会话
  unattended_mode: deny  # deny | approve — webhook/API 无人值守会话
```

> `unattended_mode` — How sessions on unattended programmatic platforms (webhook, msgraph_webhook,
> api_server) behave… `deny` blocks the command instantly… `approve` auto-approves everything in
> unattended context.

总开关是 **YOLO**：`hermes --yolo` / `hermes chat --yolo` / 会话内 `/yolo` /
`HERMES_YOLO_MODE=1`；等价配置 `mode: off`。

> ⚠️ 还有一层**硬阻断名单**（`tools/approval.py::UNRECOVERABLE_BLOCKLIST`），**YOLO 也绕不过**。
> 别指望 YOLO 能让你为所欲为，危险命令仍会被拦。

### 自触发循环（这才是"自动化"的来源，四个，都不是 bot mode 的一部分）

| 机制 | 作用 |
|---|---|
| `/goal` | judge 驱动的 Ralph loop，"keep working until done" |
| `/loop [interval]` | 定时重跑，支持 `--times N`、`--until <cond>`、`LOOP_COMPLETE` 自终止；`loops.max_ticks` 默认 100 兜底 |
| `/heartbeat every 10m …` | 会话空闲时注入 |
| `hermes cron` | **进程外持久调度**，可 **no-agent 模式**（纯脚本定时跑，零 LLM 参与）；cron 内不能再建 cron 防失控 |

---

## 4. ★ Bot Mode 在这条生产线上如何发挥最大作用

**答案：把 Bot Mode 当"角色分工"，把无人值守交给 cron no-agent + approvals。**

### 4.1 Bot 花名册（详见 `agent/BOT-ROSTER.md`）

| Bot | 职责 | 模型 pin | 关键技能 |
|---|---|---|---|
| `director` | 剧本 → 分镜清单（shotlist JSON） | 强推理模型 | 分镜拆分、节奏设计 |
| `art` | 设定图提示词 → 驱动 Qwen-Image-2.1 | 平衡模型 | 视觉描述、人物一致性 |
| `prompt-smith` | 分镜 → **H3 六段式 prompt**（严格按 03 规范） | 强指令遵从模型 | `h3-prompt-writing` |
| `qc` | 抽检产物，判定 pass/retry/reject | 多模态模型 | 视觉审查 |
| `publisher` | 打包/字幕/封面/发布 | 轻量模型 | ffmpeg、平台 API |

Bot 间通过 `message_agent` 通信；群聊用于 deliberation（比如 director 与 art 对构图有分歧时）。

### 4.2 关键架构决策：LLM 不进每视频的循环

```
阶段 1  剧本        → Bot: director        （LLM，一次性）
阶段 2  分镜        → Bot: director        （LLM，一次性）
阶段 3  设定图提示词 → Bot: art             （LLM，一次性）
阶段 4  设定图生成   → worker 批量          （无 LLM）
阶段 5  H3 prompt   → Bot: prompt-smith    （LLM，一次性，按模板生成 N 条）
阶段 6  视频生成     → worker 批量消费 JSONL（无 LLM）★ 成本与确定性的关键
阶段 7  抽检        → Bot: qc              （LLM，按 10% 抽样）
阶段 8  打包发布     → Bot: publisher       （LLM + ffmpeg）
```

**为什么这是"最大作用"：**

1. **成本**：一个 60 镜头的短片，若每个镜头都让 LLM 参与，token 成本随镜头数线性增长；
   清单化后 LLM 只跑 3–4 次。
2. **确定性**：worker 消费的是固定 JSONL，同样输入永远同样输出，可复现、可断点续跑。
3. **可并行**：阶段 4/6 的 worker 可以独立于 Hermes 进程跑，Hermes 挂了不影响生产。
4. **对应到 Hermes 的机制**：用 `hermes cron` 的 **no-agent 模式**跑 worker（零 LLM 参与），
   这正是官方为此类场景设计的功能。

### 4.3 Hermes 侧需要的配置

```yaml
# ~/.hermes/profiles/<bot>/config.yaml
approvals:
  mode: smart            # 生产环境若要全自动，改 off（等价 --yolo）
  unattended_mode: approve   # webhook/API 无人值守会话自动批准
  cron_mode: approve         # cron 任务自动批准
```

```bash
# 无人值守跑 worker（零 LLM）
hermes cron add --name h3-worker --no-agent --every 1m -- scripts/worker_tick.sh

# 让 ComfyUI 侧脚本反向驱动 Hermes（最合适的一条路）
hermes peer add h3prod --url http://127.0.0.1:8377 --key <API_SERVER_KEY>
hermes peer run h3prod --idempotency-key job-123 < task.txt   # 拿 run_id
hermes peer status <run_id> / hermes peer stop <run_id>
```

### 4.4 Hermes 的三个外部接口（供 ComfyUI 侧反向调用）

| 接口 | 协议 | 端点 |
|---|---|---|
| **API Server** | OpenAI 兼容 HTTP | `http://127.0.0.1:8642/v1/chat/completions`（需 `API_SERVER_ENABLED=true` + `API_SERVER_KEY`，`hermes gateway` 后可用） |
| **A2A** | Linux Foundation Agent2Agent v1.0，JSON-RPC 2.0 + SSE | 默认端口 9900，`/.well-known/agent-card.json` |
| **Webhooks** | HTTP 8644，HMAC 验签 | 外部事件直接触发 agent run |

---

## 5. 换 Agent 怎么办

Bot Mode 是 **Hermes 特有的**。本项目不绑定它 —— 见 `agent/TOOL-CONTRACT.md`：

- Bot 的**职责定义**在 `agent/BOT-ROSTER.md`（Markdown，任何框架都能读）
- Bot 的**能力**通过 15 个标准工具暴露（任何框架都能实现）
- 换框架时：把 BOT-ROSTER 的角色翻译成该框架的 agent/prompt/skill，接上 TOOL-CONTRACT 即可

OpenClaw 侧的对应物：plugin SDK + ClawHub 分发 + Gateway 的 channels/routines。
Claude Code / Codex 侧：直接给 `agent/SKILL.md`。
