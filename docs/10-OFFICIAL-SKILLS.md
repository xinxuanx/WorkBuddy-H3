# 10 — MiniMax 官方技能全解（短视频 + 设定图要求）

> 来源：`github.com/MiniMax-AI/MiniMax-H3` 的顶层 `skills/` 目录。
> **已全部下载到 `spec/official/skills/`**（9 技能 SKILL.md + 8 个 SKILL.cn.md + README +
> `3d-animation-short-generator/references/` 5 份 + `co-op-game-intro-generator/references/` 2 份）。
>
> ⚠️ 之前只发现了 `.agents/skills/` 与 `.claude/skills/` 两份 `h3-prompt-writing` 副本，
> **漏掉了顶层 `skills/` 目录里另外 8 个短视频专项技能**。
> 漏掉的原因：列仓库文件树时用了 `head -60` 截断，**而 `skills/` 排在 `FL2VA/`、`Ref2VA/` 之后**。
> 教训：列树必须完整，或按 `| grep` 过滤而不是截断。本文补齐。

---

## 1. 官方一共 9 个技能

`skills/README.md` 原文：**"1 prompt writing skill and 8 style-specific video generation skills"**。
8 个风格技能**自带中英双语**（`SKILL.md` + `SKILL.cn.md`），`h3-prompt-writing` 目前只有英文。

| 技能 | 用途 | 与本项目相关度 |
|---|---|---|
| **`h3-prompt-writing`** | 五种模式的提示词结构规范 | ★★★ 已 vendored |
| **`3d-animation-short-generator`** | **完整剧情动画短片流水线：简报→大纲→角色卡→场景卡→镜头表→分镜→出片→BGM→终审** | ★★★ **直接就是本项目要的** |
| `brand-promo-video-generator` | 品牌/产品/网站/店铺宣传短片 | ★★ |
| `minimalist-product-ad-generator` | 极简产品广告短片（电商/新品发布） | ★★ |
| `music-video-subtitle-generator` | AI 音乐视频 + 歌词字幕动效 | ★★ |
| `co-op-game-intro-generator` | 双人合作游戏开场/菜单动画（**含"先出审批图"环节**） | ★ |
| `papercraft-stop-motion-explainer` | 纸艺定格科普短片 | ★ |
| `paper-collage-explainer-generator` | 剪纸拼贴科普/观点短片 | ★ |
| `handdrawn-live-video-generator` | 手绘发光 + 实拍融合的超现实短片（15s / 16:9） | ★ |

### 安装（官方 CLI）

```bash
# 列出可用技能
npx skills add https://github.com/MiniMax-AI/MiniMax-H3 --list

# 全装
npx skills add https://github.com/MiniMax-AI/MiniMax-H3 --skill '*'

# 装单个
npx skills add https://github.com/MiniMax-AI/MiniMax-H3 --skill 3d-animation-short-generator
```

用的是 [vercel-labs/skills](https://github.com/vercel-labs/skills) 的 CLI。
**不装 CLI 也行** —— 直接把 `SKILL.md` 拷进你的 Agent 的 skills 目录即可（官方 README 明说
兼容 Claude Code / Claude Agent SDK / Cursor / Windsurf / Codex / LangChain / 任何能读 SKILL.md 的框架）。

---

## 2. ★ 设定图要求（官方明文，在 `3d-animation-short-generator`）

> 官方术语是 **角色卡（character card）** 与 **场景卡（environment card）**。

### 2.1 角色卡：STEP 3

**原文（SKILL.cn.md 第 138 行）：**

> 每张角色卡**在可能时为 16:9 生产参考图**。与最终渲染视频不同，**角色卡必须包含清晰可读的标注**，
> 让下游生成能正确绑定人物与道具。

必含元素（官方清单）：

- 角色名标注（英文和/或项目语言）
- 角色定位标注：主角、奶奶、小偷、搭档、施压角色等
- **主 3/4 视角**
- **正 / 侧 / 背三视图**
- 表情
- 材质 / 服装 / 道具细节
- 重要道具标注：手提包、钱包、滑板、苹果筐、围巾、鞋子、眼镜等
- 提示中重复的"**身份锁**"
- 简短视觉 ID 备注：年龄段、身材、发型、服饰色、签名道具、**不可改特征**

生成顺序：主角卡 → 对比/施压角色卡 → 可选配角卡。
风格化 3D 动画要求"角色柔和、可读、**跨图跨视频一致**"。

> ⚠️ **警告用户：后续修改已锁定的角色设计，可能需要重做镜头表、分镜、片段、正片和最终合成。**
> → 对应本项目：**设定图一旦入 REF2VA 的 `subject_definitions`，改一次要全链路重跑。**

### 2.2 场景卡：STEP 4

**原文（第 163 行）：**

> 场景卡**只能展示环境，不出现人物、人群、剪影、手、脸或角色客串**。
> 角色动作属于镜头表、单镜头分镜与单镜头视频片段，**不属于场景卡**。

必含：主环境总览 / 关键光态（日景·夜景）/ 情绪子空间 /
**连续性地标**（同场景跨镜头必须保持屏幕位置的固定物体，如厨房中岛、沙发、门框、树、邮筒）/ 环境中的重要道具

### 2.3 🔴 这与我之前的建议冲突 —— 正确用法是"分两类"

我之前在 `docs/03 §4` 建议"设定图长宽比 = 目标视频长宽比"。**这个建议需要修正**：

| 设定图类型 | 比例 | 理由 |
|---|---|---|
| **角色卡 / 场景卡**（身份与场景锚点） | **16:9** | 官方明文。要塞下三视图 + 表情 + 道具细节 + 文字标注，横幅空间才够 |
| **首帧 / 尾帧 / 关键帧图**（FL2VA、I2VA、L2VA） | **= 目标视频比例**（竖屏就 9:16） | 这些是要当实际画面用的，比例必须对齐，否则构图错位 |

**结论：两类图分开出，不要混用。** REF2VA 吃的 `<Picture N>` 主要是角色卡/场景卡（16:9 + 标注）；
FL2VA 吃的首/尾帧则按成片比例（9:16）。

> 对 Qwen-Image-2.1 的影响：出角色卡用 **16:9**（如 1920×1080 或 1536×864），
> 出首尾帧用 **9:16**（如 1088×1920）。`config/registry.yaml` 已按此分列。

### 2.4 从代码推导的硬约束（官方没写，但配置里有）

`FL2VA/processor/preprocessor_config.json`：

```json
{ "size": {"longest_edge": 16777216, "shortest_edge": 65536},
  "patch_size": 16, "temporal_patch_size": 2, "merge_size": 2,
  "processor_class": "Qwen3VLProcessor",
  "image_processor_type": "Qwen2VLImageProcessorFast" }
```

按 Qwen2VL/Qwen3VL 处理器的语义，`shortest_edge` = **min_pixels**、`longest_edge` = **max_pixels**：

| 项 | 值 |
|---|---|
| **最小像素数** | 65,536（= 256×256） |
| **最大像素数** | 16,777,216（≈ 4096×4096） |
| **尺寸对齐因子** | `patch_size × merge_size` = **16 × 2 = 32** → 宽高必须是 **32 的倍数** |
| 归一化 | mean/std = 0.5 → 映射到 [-1, 1] |

→ **设定图的宽高请取 32 的倍数**（1920×1080 是 ✅；1088×1920 是 ✅；1000×1000 是 ❌）。

其他从配置确认的事实：
- `FL2VA/model_index.json` → `sigma_shift_scales: {video: 12.0, audio: 3.0}` —— **shift 12/3 是官方写死在模型定义里的**
- `FL2VA/video_vae/config.json` → `latent_channels: 24`（印证 `f16t4d24`）
- `FL2VA/transformer/config.json` → 50 层、hidden 5376、56 头、head_dim 128、text_dim 5120

---

## 3. 官方的完整短剧流水线（`3d-animation-short-generator`）

```
STEP 0  需求 intake + 画布规划
STEP 1  项目简报
STEP 2  故事大纲（节拍 / 情绪曲线 / 台词节拍）
STEP 3  ★ 角色卡（16:9 + 标注）
STEP 4  ★ 场景卡（纯环境，无人物）
STEP 5  六列标准镜头信息表（强制，不可跳过）
STEP 5.5 自检闸门
STEP 6  单文本分镜（默认）/ 可选铅笔分镜（四象限布局）
STEP 7  视频模型选项卡 + 分辨率选项卡 + 单镜头渲染
STEP 8  全片拼接 + BGM 匹配 + 最终输出
```

> 已按 `SKILL.md` 的 `## STEP` 标题逐条核对：**实际是 STEP 0–8，没有 STEP 9**。
> STEP 5.5（自检闸门）不单独成节，写在 STEP 5 正文里。

### 3.0 STEP 6 单文本分镜（默认模式的逐镜结构，11 项）

默认**不生成任何图片** —— 一份纯文本文档承载全片分镜，成本近零且是渲染权威源。
每个镜头一个 `##` 节，字段顺序固定：

1. **镜头标题 & 时长** — `S03 / 6s`
2. **Hook 类型** — 受控词表：`setup` / `visual-joke` / `reversal` / `reveal` / `callback` /
   `suspense` / `tender` / `chase` / `expression-beat` / `climax`
3. **场景 & 角色** — 绑定确切的场景卡名与角色卡名
4. **空间锚点卡**（四项全必填）：固定地标（含屏幕相对位置）/ 角色位置（画面方位+朝向+初始姿态）/
   **已离场角色状态** / 光照基线
5. **连续性** — `Continuity from S(N-1)` + `Continuity to S(N+1)`
6. **双绑定** — `[char:名] [scene:名] [hook:类型]`（渲染前剥离）
7. **逐 panel 四象限内容**（每秒一块）：`Timecode` / `Pose + Expression`（最大块，视频模型真正读的视觉节拍）/
   `Camera` / `Audio + Anchor` + Performance 注记
8. **面板数规则**：3s→3 / 4s→4 / 5s→5 / 6s→6 / 7s+→每秒一块，**必须无时间空隙地铺满全镜**
9. **逐 panel 绑定** — 锁外貌/脸/发型/体型/服装/签名道具/角色身份 + 场景的环境/道具/地标/动线
10. **可选 ASCII 布局块**（免费，强烈推荐）—— 仅供人扫读，**视频模型不读它**
11. **分镜专用标记** — `[BEAT]` 关键节拍；`[HANDOFF → ...]` 交接

> 铅笔图分镜是**可选**的可视化模式，且官方明说"纯黑白线稿、不上色、不做最终渲染光照"，
> 且**仅供人审** —— 文本分镜才是权威。

**每一步结束都有"用户选项卡"**（批准继续 / 重生成 / 调整 / 返回上一步）——
这与本项目 `agent/BOT-ROSTER.md` 的 Bot 分工天然契合：
选项卡 = Bot 向人（或向 director Bot）请求裁决的界面。

### 3.1 六列标准镜头信息表（STEP 5，强制）

| 镜头编号&时长 | 连续性衔接 | 参考锚点（空间+身份） | Hook 类型 | 镜头描述（每秒指令） | 音频与对白轨 |
|---|---|---|---|---|---|

- 镜头编号格式：`S03 / 6s`
- **参考锚点**四子字段全必填，其中：
  `固定地标` — 来自场景卡的确切命名地标 + 相对画面位置（如 `door-frame: 右侧 1/3`）
- **双绑定标记**：`[char:角色名-01] [char:角色名-02] ... [scene:场景名] [hook: visual-joke]`

### 3.2 三个"权威源"（渲染时不可违背）

1. **单文本分镜文档** = 逐镜权威（叙事/构图/运镜/编排/每秒时间/镜头号）
2. **角色卡** = 权威身份源
3. **场景卡** = 权威环境源

> 🔴 **渲染视频前必须剥离所有分镜双绑定标签**
> （`[char:…]` / `[scene:…]` / `[shot:…]` / `[dur:…]` / `[hook:…]`）
> —— 这些是分镜专用参考标记，**不能出现在最终 prompt 里**。

### 3.3 视频模型与分辨率选项卡（渲染前的强制门）

**模型选项卡：**
- **H3（推荐默认）** — 强项：视觉包装、动效图形、**文字/UI 清晰度**、多模态上下文理解、性价比
  （2K 约同类旗舰 1/3 价格，768P 约 1/2）。**原生双声道音视频，单片段最长 15s @ 2K**。
  最适合：设计语言强的 3D 动画短片、文字/字幕/UI 元素、动效转场、对话驱动镜头。
- **Seedance 2.0（回退）** — 强项：电影感镜头、复杂运镜、弹性表演、动作张力。
  适合追逐、闹剧、climax 镜头。→ **这正是 H3 的短板所在**
- **逐镜混合** — 镜头表某行加 `video_model: H3` 或 `video_model: Seedance2` 字段

**分辨率选项卡：**
- **768P** — H3 首推，性价比高
- **2K** — H3 默认质量（成本更高）
- 1080p / 720p — Seedance 2.0
- 匹配项目 / 自定义

### 3.4 H3 失败回退阶梯（可直接抄进 `orchestrator/worker.py`）

| 次数 | 动作 |
|---|---|
| 第 1 次重试 | 用直接引用表格中 `参考锚点` 块的强化 H3 prompt 重渲染 |
| 第 2 次重试 | 把该镜缩到 **≤6s**，砍掉的秒拆到 Step 5 的新相邻行，重跑自检再渲 |
| 第 3 次重试 | 把这一镜**切到 Seedance 2.0** |
| 连续 3 次失败 | **暂停**并问用户：切模型 / 放宽要求（去掉一个道具、简化动作、降低 hook 强度）/ 跳过并标 `placeholder: missing clip` / 手动提供参考视频 |

（Seedance 侧的第 2 次重试是"**去掉参考图，纯文本生成**"—— 说明参考图确实可能成为失败源。）

---

## 4. 官方 API 形态（从可复现脚本提取）

`scripts/readme/*.sh` 里的真实 payload：

```json
{
  "task": "ref2va",
  "prompt": "subject_definitions:\n...",
  "conditions": [
    { "type": "image", "uri": "https://.../xxx.png", "role": "keyframe", "frame_index": 0 },
    { "type": "video", "uri": "https://.../xxx.mp4", "role": "reference" },
    { "type": "audio", "uri": "https://.../xxx.mp3", "role": "reference" }
  ],
  "target": { "short_edge": 768, "aspect_ratio": "auto", "duration_seconds": 8 },
  "seed": 0
}
```

要点：
- 图片用 `role: "keyframe"` + `frame_index`（首帧 0）；纯参考用 `role: "reference"`
- `target.aspect_ratio: "auto"` —— **可让模型自动推断**（本项目做竖屏时应显式写 `9:16`）
- `target.short_edge: 768` —— 与 README"短边默认 768px"一致
- `uri` 支持 `file://` 本地路径（容器内需挂载目录）

---

## 5. 对本项目的影响（要改什么）

### 已做
- ✅ 9 个官方技能全部下载到 `spec/official/skills/`
- ✅ 设定图拆成两类（角色/场景卡 16:9 vs 首尾帧 9:16），写入 `config/registry.yaml`
- ✅ 32 倍数对齐、min/max 像素约束写入 `docs/03 §4`

### 建议调整
| 项 | 现状 | 建议 |
|---|---|---|
| 流水线 | 自建 8 步（剧本→分镜→设定图→prompt→生成→抽检→打包） | **对齐官方 STEP 1–9**，特别是"六列镜头表"和"三权威源" |
| 设定图比例 | 统一按目标视频比例 | **角色卡/场景卡改 16:9**，首尾帧保持目标比例 |
| 分镜标签 | 无 | 引入 `[char:]`/`[scene:]` 双绑定，**渲染前剥离** |
| 失败重试 | worker 只有"降级分辨率/帧数" | **抄官方 4 级阶梯**，第 3 级换模型、第 4 级暂停等人 |
| 分辨率决策 | 写死在 tier | 加"分辨率选项卡"式的人工确认门（首条片段渲染前） |
| H3 短板 | 未记录 | **H3 弱于高强度表演与复杂运镜** → 此类镜头考虑 Seedance 2.0 或降要求 |

### 未解决
- 官方技能里的"画布/选项卡"交互是给对话式 Agent 设计的；
  本项目要**无人值守**，需把"选项卡"翻译成 `job_ledger` 的状态与人工抽检队列（见 `docs/08-RUNBOOK.md` 阶段 4）。
