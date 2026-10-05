# 00 — 总体架构

---

## 1. 设计目标

> **换任何一个 Agent 框架，读完本仓库都能把这条生产线跑起来。**

由此推出三条不可妥协的原则：

1. **能力外置。** 剧本/分镜/提示词/H3 规范的**知识**放在仓库文件里，不放在 Agent 的"脑子"里。
   Agent 只是读者与执行者。
2. **工具契约化。** Agent 与生产线之间只有一层薄接口（15 个工具），换框架 = 重新实现这 15 个工具。
3. **LLM 不进每视频循环。** 批量执行由确定性代码完成，Agent 只在阶段边界介入。

---

## 2. 五层架构

```
┌─────────────────────────────────────────────────────────────┐
│ L5  Agent（Hermes / OpenClaw / Claude Code / 任意框架）        │
│     读 agent/SKILL.md，按 agent/TOOL-CONTRACT.md 调工具        │
└───────────────────────┬─────────────────────────────────────┘
                        │ 15 个标准工具
┌───────────────────────▼─────────────────────────────────────┐
│ L4  Agent 适配层   ← 换 Agent 只改这一层                      │
│     MCP server / CLI / OpenAPI HTTP（三选一，可并存）          │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│ L3  Orchestrator                                             │
│     job_ledger.py（SQLite 账本，状态机，断点续跑）             │
│     worker.py（常驻消费器，队列深度 1–3，双超时，重试分级）    │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│ L2  ComfyUI 适配层                                           │
│     comfy_client.py（/prompt + /ws + /history + /view）      │
│     build_workflow.py（槽位模板 → API JSON，含硬校验）        │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│ L1  ComfyUI Runtime（comfy-cli 托管）                         │
│     MiniMaxH3Director + 稀疏注意力 + 融合权重 + Qwen/Krea 支线 │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 数据流

```
剧本 (txt)
   │ Bot: director
   ▼
shotlist.json          ← spec/shotlist.schema.json
   │ Bot: art
   ▼
设定图提示词 (jsonl)
   │ worker 批量（无 LLM）→ Qwen-Image-2.1
   ▼
设定图 (png) × N
   │ Bot: prompt-smith（按 03 规范）
   ▼
H3 prompt (jsonl)      ← 六段式 / 三段式
   │ worker 批量（无 LLM）→ ComfyUI + MiniMax-H3
   ▼
片段 mp4 × N
   │ Bot: qc（10% 抽样）
   ▼
过检片段
   │ Bot: publisher（ffmpeg / 字幕 / 封面）
   ▼
成片
```

**关键：所有 LLM 参与的箭头都是"一次性"的（一个阶段一次调用）；
所有"× N"的批量环节都没有 LLM。**

---

## 4. 配置驱动

`config/registry.yaml` 是**唯一配置源**。它决定：

- 硬件档位（t10 / t16 / t24 / t48）→ 分辨率、步数、VAE、启动参数
- H3 权重注册表 → 每个权重文件的模式覆盖、是否融合 turbo、推荐采样参数
- 稀疏注意力方案 → SLA / Veda / none（互斥）
- 工作流变体矩阵 → 9 个变体的组合定义
- 设定图模型 → Qwen-Image-2.1 / Krea 2 的角色与参数
- H3 参考资产硬限制 → 用于提交前校验

**新增一台机器 = 加一个 tier。新增一个权重 = 加一条记录。都不改代码。**

---

## 5. 硬校验（构建期拦截，不产出坏结果）

`comfy/build_workflow.py` 中实现的校验规则：

| 规则 | 触发 | 处置 |
|---|---|---|
| **参考资产超限** | 图 >9 / 视频 >3 / 音频 >3 / 总 >12 | 报错 |
| **单段时长越界** | 参考片段 <2s 或 >15s | 报错 |
| **4 步 + REF2VA + 强身份** | steps=4 且 mode=ref2va 且 require_identity_fidelity | **强制报错**（官方已知漂移问题） |
| **注意力方案互斥** | 同时请求 sla 与 veda | 报错 |
| **权重不支持该模式** | 权重的 `modes` 不含请求 mode | 报错并列出该权重支持的模式 |
| **档位 vs 权重体积** | tier.max_weight_bytes < 权重 size | 警告（仍可跑，但会很慢） |
| **Veda 版本门槛** | attention=veda 且 ComfyUI < 0.38 | 报错 |

---

## 6. 模块职责边界

| 模块 | 负责 | **不负责** |
|---|---|---|
| `agent/` | 角色定义、工具契约、执行手册 | 不写业务代码 |
| `comfy/adapter/` | 与 ComfyUI 的通信、失败重试 | 不理解业务语义 |
| `comfy/build_workflow.py` | 模板 → API JSON、参数校验 | 不与 ComfyUI 通信 |
| `comfy/templates/` | 槽位化的图结构 | 不含具体参数值 |
| `orchestrator/` | 任务状态、消费、归档 | 不生成提示词 |
| `spec/` | 结构定义与配方 | 不执行 |
| `config/` | 全部可调参数 | 不含逻辑 |

---

## 7. 可观测性

每个 job 记录（落 SQLite + JSONL 日志）：

```
job_id · prompt_id · client_id · workflow_hash · variant · mode
seed · steps · shift · res · weight · attention
t_submit · t_first_event · t_done · peak_vram · retry_count · status
```

- 失败时**把当时的 API JSON 一并落盘**，保证可复现
- `/system_stats` 采样峰值显存
- WS 事件全量落 JSONL

---

## 8. 为什么不做成一个大 Agent

| 方案 | 问题 |
|---|---|
| 一个全能 Agent 端到端 | token 成本随镜头数线性增长；不可复现；Agent 挂了整线停 |
| Agent 全程在线轮询 | 长任务阻塞；stdio MCP 会卡 |
| **阶段边界 + 常驻 worker** ✅ | LLM 只跑几次；执行确定性；可断点续跑；Agent 与生产解耦 |

这就是"Bot Mode 最大作用"的落点：**Bot 负责决策与创作，worker 负责执行**。
