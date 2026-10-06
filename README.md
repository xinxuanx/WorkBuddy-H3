# WorkBuddy H3 — Agent + ComfyUI 全自动短视频生产线

**仓库：<https://github.com/xinxuanx/WorkBuddy-H3>**

> 目标：**换任何一个 Agent 框架，读完本仓库都能把这条生产线跑起来。**
> 主生成模型：MiniMax-H3（33B 单流 Omni-Transformer，视频+音频联合生成）
> 参考图模型：Qwen-Image-2.1（设定图/角色一致性/文字）
> 风格板模型：Krea 2 Turbo / DaSiWa 微调版
> 编排层：ComfyUI（原生 H3 支持）+ 本仓库的适配层与作业账本

---

> 📦 **MiniMax 官方 9 个技能已全部内置**：`spec/official/`（17 个 md，316KB）
> - `h3-prompt-writing` —— 提示词规范（来自 `.agents/skills/` 与 `.claude/skills/`）
> - **8 个短视频专项技能**（来自顶层 `skills/`）：`3d-animation-short-generator`、
>   `brand-promo-video-generator`、`minimalist-product-ad-generator`、
>   `music-video-subtitle-generator`、`co-op-game-intro-generator`、
>   `papercraft-stop-motion-explainer`、`paper-collage-explainer-generator`、
>   `handdrawn-live-video-generator` —— **均带中文版 `SKILL.cn.md`**
>
> 官方安装：`npx skills add https://github.com/MiniMax-AI/MiniMax-H3 --skill '*'`
> 也可直接复制 `SKILL.md` 到任意 Agent 的 skills 目录（官方明说兼容 Claude Code / Cursor /
> Windsurf / Codex / LangChain / 任何能读 SKILL.md 的框架）。
>
> **权威提示词规范**：`references/base-en.txt`（222 行）+ `references/ref-en.txt`（341 行），
> **与本文档冲突时以它们为准**。
> **设定图要求**见 [docs/10-OFFICIAL-SKILLS.md §2](docs/10-OFFICIAL-SKILLS.md) ——
> 官方明文规定角色卡/场景卡用 **16:9**，首尾帧才跟目标视频比例。

## 0. 三句话结论（先读这个）

1. **H3 基座选「融合/混合权重」，不选原版。** 你只有 RTX 3080 10GB，原版 FL2VA 与 Ref2VA 是两个各约 20GB 的独立权重，切换任务就要换模型；融合权重一个文件同时跑两种模式，是 10GB 卡上唯一现实的选择。（详见 [docs/02-MODEL-SELECTION.md](docs/02-MODEL-SELECTION.md)）
2. **设定图模型用 Qwen-Image-2.1 原版，不用 Krea-2。** H3 的 REF2VA 需要「同一角色的多张设定图」保持身份一致，而 Krea 2 官方明确把「通用 image reference」列为未来工作、当前只支持风格参考。Krea 2 放在风格板/封面位。（详见 [docs/02-MODEL-SELECTION.md](docs/02-MODEL-SELECTION.md)）
3. **注意力加速只用 SLA（ComfyUI 原生），JEV 直接砍掉。** JEV 不是注意力方案，是 LLM 预算分配器，实测相对固定 SLA **反而慢 6.95s**，作者自己也证伪了。Veda 与 SLA **互斥**，做成两条链、构建期选择，不要运行时混用。（详见 [docs/06-WORKFLOW-MATRIX.md](docs/06-WORKFLOW-MATRIX.md)）

---

## 1. 新人/Agent 的阅读顺序

| 顺序 | 文件 | 你要拿到什么 |
|---|---|---|
| 1 | 本 README | 全局地图与三条硬结论 |
| 2 | [docs/01-HARDWARE-AND-ENV.md](docs/01-HARDWARE-AND-ENV.md) | 你的显卡属于哪个档位，该走哪条路 |
| 3 | [docs/02-MODEL-SELECTION.md](docs/02-MODEL-SELECTION.md) | 每个模型文件放哪个目录、选哪个变体 |
| 4 | [docs/03-H3-PROMPT-SPEC.md](docs/03-H3-PROMPT-SPEC.md) | **写提示词的唯一规范**，不按这个写必崩 |
| 5 | [docs/06-WORKFLOW-MATRIX.md](docs/06-WORKFLOW-MATRIX.md) | 该用 9 个工作流变体里的哪一个 |
| 6 | [docs/04-COMFYUI-INTEGRATION.md](docs/04-COMFYUI-INTEGRATION.md) | 代码怎么调 ComfyUI |
| 7 | [agent/TOOL-CONTRACT.md](agent/TOOL-CONTRACT.md) | **换 Agent 时唯一需要重新实现的接口** |
| 8 | [docs/08-RUNBOOK.md](docs/08-RUNBOOK.md) | 从零到出片的逐步操作 |

如果你是一个 Agent：直接读 [agent/SKILL.md](agent/SKILL.md)，那是给你的执行手册。

---

## 2. 目录结构

```
F:\Agent H3\
├── README.md                      ← 你在这里
├── config/
│   └── registry.yaml              ← 硬件档位 + 模型注册表 + 工作流变体（唯一配置源）
├── docs/
│   ├── 00-ARCHITECTURE.md         总体架构（5 层）
│   ├── 01-HARDWARE-AND-ENV.md     硬件分层与环境准备
│   ├── 02-MODEL-SELECTION.md      模型选型结论与决策依据
│   ├── 03-H3-PROMPT-SPEC.md       H3 提示词 / 设定图 / 参考资产规范
│   ├── 04-COMFYUI-INTEGRATION.md  Agent ↔ ComfyUI 交互协议与参考实现
│   ├── 05-AGENT-AND-BOT-MODE.md   Agent 框架与 Hermes Bot Mode 的真实作用
│   ├── 06-WORKFLOW-MATRIX.md      工作流矩阵（SLA/Veda × fused/lora/none）
│   ├── 07-SOURCES.md              全部调研资料与出处
│   ├── 08-RUNBOOK.md              执行手册
│   ├── 09-NODE-INVENTORY.md       ★ 实测节点清单（从你本地可跑的工作流提取）
│   └── 10-OFFICIAL-SKILLS.md      ★ 官方 9 个技能全解 + 设定图要求 + 短剧流水线
├── agent/
│   ├── SKILL.md                   给 Agent 加载的执行手册
│   ├── TOOL-CONTRACT.md           工具契约（换 Agent 只改这一层）
│   └── BOT-ROSTER.md              多 Bot 角色分工定义
├── spec/
│   ├── official/                  ★ MiniMax 官方 h3-prompt-writing 技能（原样 vendored）
│   │   └── h3-prompt-writing/{SKILL.md, references/base-en.txt, references/ref-en.txt, agents/openai.yaml}
│   ├── shotlist.schema.json       分镜清单结构定义
│   └── prompt_recipe.md           提示词配方（含逐字照抄的指令行）
├── comfy/
│   ├── adapter/comfy_client.py    ComfyUI 客户端（提交/监听/取件/重试）
│   ├── build_workflow.py          模板 → API JSON 构建器
│   └── templates/                 槽位化工作流模板
├── orchestrator/
│   ├── job_ledger.py              作业账本（SQLite，可断点续跑）
│   └── worker.py                  常驻消费器
├── spec/
│   ├── shotlist.schema.json       分镜清单结构定义
│   └── prompt_recipe.md           提示词配方（可复用模板）
└── workflows/                     构建产物（生成好的 API JSON）
```

---

## 3. 架构一句话

```
Agent(任意框架)
   │  Tool Contract（15 个工具）
   ▼
Orchestrator（作业账本 + 常驻 worker）
   │  ComfyUI HTTP + WebSocket
   ▼
ComfyUI（MiniMaxH3Director + 稀疏注意力 + 融合权重）
   │
   ├─ 支线 A：Qwen-Image-2.1 → 设定图
   └─ 支线 B：Krea 2 → 风格板/封面
```

**核心设计原则：LLM 不进每视频的循环。**
Agent 只在**阶段边界**介入（剧本 → 分镜 → 设定图提示词 → H3 prompt → 抽检 → 打包），中间的批量执行由常驻 worker 消费 JSONL/SQLite 任务表完成。这既省钱又保证确定性。

---

## 4. 当前硬件实况（已实测）

| 项 | 值 |
|---|---|
| GPU | NVIDIA GeForce RTX 3080 **10 GB** |
| 驱动 | 610.88 |
| 已下载模型 | `minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot` (21GB)、`minimax_h3_hybrid_fl2va_ref2va_b25-49-int8` (21GB)、`minimax_h3_hybrid_fl2va_ref2va_b30-49-int8` (21GB)、`DasiwaKrea2TurboRaw_darkdesireV3TurboUC_int4/int8` |
| ComfyUI 主程序 | 尚未解压安装（F 盘根目录有 `ComfyUI-portable-nvidia.7z`） |

> **10GB 是本项目的头号约束。** 所有选型、分辨率、步数决策都围绕它展开，见 [docs/01-HARDWARE-AND-ENV.md](docs/01-HARDWARE-AND-ENV.md)。

---

## 5. 常见问题直达

- **MiniMax-H3 用原版还是微调/融合版？** → [02-MODEL-SELECTION.md §2](docs/02-MODEL-SELECTION.md)
- **设定图用 Krea-2 还是 Qwen-Image-2.1？** → [02-MODEL-SELECTION.md §3](docs/02-MODEL-SELECTION.md)
- **H3 对设定图和提示词到底有什么要求？** → [03-H3-PROMPT-SPEC.md](docs/03-H3-PROMPT-SPEC.md)
- **注意力加速现在 ComfyUI 原生支持了吗？** → [06-WORKFLOW-MATRIX.md §1](docs/06-WORKFLOW-MATRIX.md)
- **Veda 和 SLA 做一个工作流还是两个？** → [06-WORKFLOW-MATRIX.md §3](docs/06-WORKFLOW-MATRIX.md)
- **融合 turbo 和没融合 turbo 的工作流怎么切换？** → [06-WORKFLOW-MATRIX.md §4](docs/06-WORKFLOW-MATRIX.md)
- **Bot Mode 到底能干嘛？** → [05-AGENT-AND-BOT-MODE.md](docs/05-AGENT-AND-BOT-MODE.md)

---

## 6. 许可证风险提示（必读）

| 模型 | 许可 | 商用风险 |
|---|---|---|
| MiniMax-H3 | 开源（详见官方仓库） | 需自行核对 MiniMax 许可条款 |
| Qwen-Image-2.1 | **Qwen Research License，仅非商用研究/评估** | ⚠️ **商用需向 Qwen 另行取得商业许可**；合规替代是 Apache-2.0 的 Qwen-Image-Edit-2509 |
| Krea 2 | Krea 2 Community License，**年营收 < 100 万美元可免费商用** | 超阈值需企业许可；分发时名称须以 "Krea" 开头 |
| DaSiWa 系列 | 依 Civitai 页面条款 | 需自行核对 |

> 若本项目要商用落地，**设定图环节要么申请 Qwen 商用授权，要么切到 Apache-2.0 路线**。这是唯一可能卡住整条线的合规点。
