# 03 — H3 提示词与设定图规范

> **权威来源已原样 vendored 到本仓库：**
> - `spec/official/h3-prompt-writing/SKILL.md`
> - `spec/official/h3-prompt-writing/references/base-en.txt`（T2VA/I2VA/FL2VA/L2VA，222 行）
> - `spec/official/h3-prompt-writing/references/ref-en.txt`（Ref2VA 全参考模式，341 行）
> - `spec/official/h3-prompt-writing/agents/openai.yaml`
>
> 来源：`github.com/MiniMax-AI/MiniMax-H3` 的 `.agents/skills/` 与 `.claude/skills/`。
> **本文档是那两份规范的中文索引；有冲突时以 `spec/official/` 原文为准。**

---

## 0. 官方技能：有，且可直接安装

仓库里有**两份完全相同**的技能副本（字节数一致）：

```
.agents/skills/h3-prompt-writing/     ← 通用 Agent 约定（AGENTS.md / agentskills.io 风格）
.claude/skills/h3-prompt-writing/     ← Claude Code 约定
```

官方 frontmatter 原文明确写了它**不绑定任何厂商**：

> compatibility: Portable to any agent that can read local files — no external API calls,
> MiniMax Hub tools, or proprietary runtime required. The `agents/openai.yaml` file only adds
> optional ChatGPT/Codex UI metadata; **it does not restrict the skill to OpenAI agents**.

### 安装

| 目标 | 做法 |
|---|---|
| **Claude Code** | `cp -r spec/official/h3-prompt-writing ~/.claude/skills/`（或项目级 `.claude/skills/`） |
| **Hermes Agent** | 技能兼容 `agentskills.io` 开放标准 → 放到 Hermes 的 skills 目录即可 |
| **本项目的 Bot** | 直接让 Bot 读 `spec/official/h3-prompt-writing/references/*.txt`（见 `agent/BOT-ROSTER.md` 的 `prompt-smith`） |
| **任意框架** | 复制目录，在 system prompt 里指向 `SKILL.md` |

`agents/openai.yaml` 只是 UI 元数据（显示名 + 默认提示词 `$h3-prompt-writing`），**删掉也不影响**。

### SKILL.md 的工作流（原文）

1. 识别输入模式：T2VA / I2VA / FL2VA / L2VA / Ref2VA
2. base 文本/关键帧模式 → 读 `references/base-en.txt`
3. 全参考模式 → 读 `references/ref-en.txt`
4. **保持字段名、段落顺序、标签、时间记法与所选指南完全一致**

---

## 1. Base 模式（T2VA / I2VA / FL2VA / L2VA）

### 1.1 最终结构：**指令行 + 空行 + 三个核心字段**

> ⚠️ **指令必须是 prompt 的第一行，后跟一个空行，然后才是核心字段。**

| 模式 | 指令行（**逐字照抄**，只替换 N 和 S.SS） |
|---|---|
| **T2VA** | *无指令行*，直接开始三个核心字段 |
| **I2VA** | `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` |
| **FL2VA** | `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.` |
| **L2VA** | `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.` |

> 🔴 **尖括号用法不一致，别写错：**
> - **I2VA / L2VA 用尖括号**：`<Picture 1>`、`[Shot 1]`
> - **FL2VA 不用尖括号**：`Picture 1 (from Shot 1)` —— 官方原文就是裸写
>
> `N` = 实际最后一个镜头的序号；`S.SS` = 有效时长，**精确到两位小数**。

### 1.2 三个核心字段

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

| 字段 | 内容 | 长度 |
|---|---|---|
| `integrated_multimodal_description` | 画面、动作、镜头、说话人、对白、演唱、以及**故事内（diegetic）声音**，按时间线展开 | 主体 |
| `overall_soundscape` | 全片的环境音、物理动作声、非语言人声 | **1–4 句英文**，一段连续文字 |
| `non_diegetic_music` | 角色听不到、只有观众能听到的配乐 | **1–3 句英文** |

**N/A 规则（不是"留空就行"）：**
- `overall_soundscape` 用 `N/A` —— **仅在用户明确要求全片静音时**
- `non_diegetic_music` 用 `N/A` —— 无配乐时

> 对白、演唱、以及角色能听到的装置音乐（收音机/电视/手机）属于 **diegetic**，
> 必须写在 `integrated_multimodal_description` 里，**不能**放进 `non_diegetic_music`。

### 1.3 四种 base 模式的写法差异

| 模式 | 图片角色 | 官方推荐结构 |
|---|---|---|
| **T2VA** | 无图，纯文本构建完整时间线 | — |
| **I2VA** | `<Picture 1>` = 0.00s 的实际首帧，属 `[Shot 1]` | 首帧锚点 → 动作起始 → 持续发展 → 结果/反应 |
| **FL2VA** | Picture 1 开头、Picture 2 结尾 | 首帧状态 → 可见的中间变化 → 差异逐步收窄 → 尾帧状态 |
| **L2VA** | `<Picture 1>` = **最后一帧**，属最后的 `[Shot N]`，**不属于 Shot 1** | 合理的前置状态 → 明确的动作与过渡路径 → 最后一镜逐步收敛 → 尾帧落地 |

> **FL2VA 官方明确倾向单镜头**（"generally favors a single shot"），只有用户明确要求时才多镜。
> **L2VA 要靠推断**：从尾帧反推一个合理的前置状态，再逐步收敛到尾帧。

### 1.4 风格定调的位置（两种模式不一样）

- **Base 模式**：风格写在 `[Shot 1]` **之后** —— `[Shot 1] Live-action, cinematic, a medium-wide shot frames...`
- **Ref2VA**：风格写在 `[Shot 1]` **之前**，用 1–2 句英文单独成段

常用风格词：`Cinematic` / `live-action` / `2D-animated` / `3D CG` / `claymation` / `watercolor` / `vintage film`
（有参考图时**从参考图推导**风格，不要自己选）

### 1.5 分镜与剪切

- **`[Shot 1]` 不加时间戳**；后续 `[Shot N] At MM:SS.mmm, ...`，时间严格递增且落在片长内
- 普通剪切用：`the camera cuts to` / `the shot cuts to` / `the shot transitions to` / `the shot changes to` / `the shot switches to`
- 交叉溶解、淡入淡出、划变**仅在用户明确要求时**使用
- 一次剪切必须带来新信息（主体/空间/状态/视点/时间）；只改距离或轻微角度请**用运镜**

### 1.6 运镜：类型 + 幅度 + 速度（三维）

| 维度 | 可用表达 |
|---|---|
| **类型** | `Zoom In/Out`（变焦，机身不动）、`Push In/Pull Out`（推拉，机身移动）、`Pan Left/Right`（原地水平摇）、`Truck Left/Right`（水平平移）、`Tilt Up/Down`（原地垂直摇）、`Pedestal Up/Down`（整机升降）、`Arc Shot`（环绕）、`Tracking Shot`（跟拍）、`Static Shot`（全静止）、`Shake Slightly/Strongly`、`POV`、`Roll Clockwise/Counterclockwise` |
| **幅度** | `with small amplitude` / `with large amplitude` |
| **速度** | `at slow speed` / `at fast speed` |

> 中等幅度、正常速度**通常省略**。
> **必须写成句子里的自然英文动作，不要在句末堆标签**：
> ```
> ✅ The camera pushes in with small amplitude at slow speed toward the folded letter in her hands.
> ❌ ... [push_in, small, slow]
> ```

### 1.7 说话人、对白、演唱

- 稳定 ID：`(S1)` `(S2)`；多人同时说/唱用复合 ID `(S1,S2)`
- **同一说话人跨镜头保持同一 ID**；不发声的角色不给 ID
- 说话人首次出现时，要在 `<d>` **外面**给足身份信息（角色类型、年龄、性别、是否出画、音高、音色、语速、口音）
- `<d>` 内**只放语言标签 + 原始对白**，逐字保留原文与标点，**不翻译不改写**
  ```text
  The young woman with a quiet, breathy voice (S1) says: <d>[English] I get off at the next station.</d>
  The two children (S1,S2) shout together, <d>[English] Wait for us!</d>
  ```
- **画外音**：必须用固定短语 `says in an off-screen voiceover`，且紧接着声明**嘴唇闭合**
  ```text
  The man (S1) says in an off-screen voiceover: <d>[English] I still remember that road.</d> while his lips remain completely closed.
  ```
- **对白跨剪切**：两段连接处都用 `<scenetrans>`，并显式说明声音跨镜连续
  （`continues seamlessly across the cut` / `continues uninterrupted into the next shot` /
  `carries over from the previous shot` / `remains audible across the transition`）
- **被片尾截断**的说话用 `<cutoff>`
- 听不清处写 `[unclear]`，**不要猜**
- 标点标准化为 `, . ? !`，去掉波浪号、emoji、装饰性重复标点；完整句结尾加 `.`/`?`/`!` 再 `</d>`

### 1.8 画面内文字

横幅、招牌、标签、字幕、霓虹字等**实际出现在画面里**的文字，用**英文双引号**包裹，
保留原文字与标点，**不翻译**：

```text
A red neon sign reading "营业中" glows above the doorway.
```

---

## 2. Ref2VA 全参考模式（六段式，顺序固定）

```
subject_definitions → summary → retention_analysis
→ detailed_description → overall_soundscape → non_diegetic_music
```

### 2.1 四类标签

| 标签 | 含义 |
|---|---|
| `<Subject N>` | 从参考资产抽象出的**可复用可见内容**（人/物/场景/服装/道具/风格/动作/表情/姿态） |
| `<Picture N>` | 参考图，作为**具体目标帧或分镜锚点** |
| `<Video N>` | 参考视频，提供剪辑源、续写起点、或整片时间结构 |
| `<Audio N>` | 被复制或被引用的音频信号 |

> 标签一旦指定，**在全部六个段落中含义保持一致**。
> `<Video N>` 与 `<Audio N>` **独立编号**，索引不表示配对关系（同一视频可同时是 `<Video 1>` 和 `<Audio 2>`）。

**`<Picture N>` 何时独立建条目**：只有当作**首帧/关键帧/尾帧/编辑关键帧/构图锚点**时才独立；
若只用来定义角色、场景、服装、风格 → **内联进对应的 `<Subject N>`**，不单建条目。

```text
✅ <Subject 1> is the young woman in <Picture 1>, with long dark hair, a blue cardigan...
✅ <Picture 2> is the first frame of [Shot 1], showing a woman seated beside a café window.
✅ <Picture 3> is a storyboard reference for [Shot 1] and [Shot 2], defining their viewpoint...
```

### 2.2 `summary` —— **必须以方括号任务类型前缀开头**

| 任务类型 | 何时用 |
|---|---|
| `keyframe completion` | 图作为首帧/关键帧/尾帧/编辑关键帧等具体帧锚点 |
| `reference generation` | 图/视频/音频只提供角色、场景、风格、动作、运镜、分镜等**生成引导**，不是具体帧也不是被编辑/续写的源 |
| `video editing` | 直接修改已有源视频（编辑图片或在静帧间生成**不算**） |
| `video continuation` | 从已有源视频末端继续、延长、恢复或转场 |
| `audio reuse` | 完整或部分复用同一音频信号 |
| `audio reference` | 不复制信号，只引用音乐风格/音色/对白内容/音效质感/节拍/连续性 |

组合用 ` + `，不重复：

```text
[reference generation + audio reference] The target video shows <Subject 3> eating a cookie in <Subject 1>...
[video continuation + keyframe completion] ...
[video editing + audio reuse] ...
```

- `summary` 只能用已定义的标签，**不得引入新标签**
- 编辑类任务在前缀后接：`The target video is an edited version of <Video 1>.`
- 一段短英文段落即可

### 2.3 `retention_analysis` —— **两套标记，别混用**

**可见内容**（`<Subject N>` / `<Picture N>` / `<Video N>`）：

| 标记 | 含义 |
|---|---|
| `fully_preserved` | 定义的角色被完整保留 |
| `partially_preserved` | 仍在使用，但部分已定义特征被改变或只部分保留 |
| `attribute_transfer` | 参考特征迁移到另一个可识别的目标主体 |
| `weak_reference` | 只保留风格/类别/构图/氛围的宽泛相似 |

**音频**（`<Audio N>`）—— 🔴 **是另一套**：

| 标记 | 含义 |
|---|---|
| `fully_copy` | 完整源音频作为目标视频的完整最终音轨 |
| `partially_copy` | 只复制部分时间线或选中音轨层，或复制后有增删替换 |
| `reference` | 不直接复制，只引用音色/节奏/音乐风格/对白内容/声音质感 |
| `weak_reference` | 只保留类别或氛围的宽泛相似 |

格式（每个标签一行）：

```text
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - ...
<Picture 2> ([Shot 1] first frame): fully_preserved - ...
<Video 1> (cut and pacing structure): weak_reference - ...
<Audio 1>: fully_copy - <Audio 1> is reused 1:1 as the target video's complete final audio track.
```

> **不要在 `retention_analysis` 里写 `(Sx)`。**
> 目标视频里新增的动作/背景/情节**不算**参考保真度的损失。

### 2.4 `detailed_description` —— 主体

- 全参考模式的主字段是 **`detailed_description`**（不是 `integrated_multimodal_description`）
- 风格在 `[Shot 1]` **之前**用 1–2 句英文单独定
- 生成任务通常 **350–500 英文词**；对白密集时优先保证完整说话时间线，不硬凑字数
- 视频编辑类描述随源视频复杂度伸缩，不受此字数区间约束
- 首次出现 `<Subject N>` 时描述其参考特征、画面位置、当前动作；后续镜头沿用同一标签不重新定义
- 具体帧锚点的自然写法：`the shot begins from <Picture 1>` / `the shot's keyframe corresponds to <Picture 2>` / `the shot ends on <Picture 3>`
- **说话时要同时保留视觉标签和说话人 ID**：`<Subject 2> (S1) turns toward the woman and says, <d>[English] ...</d>`
- 被复用的 BGM/完整配乐中的声音提示用 `<Audio N>` 作为声源，**不要凭空发明 `(Sx)`**；
  由具体人物/角色/旁白发声的才分配 `(Sx)`
- `retention_analysis` 里不写 `(Sx)`；`(Sx)` 按目标视频中**实际发声事件顺序**分配一次，之后复用

### 2.5 `overall_soundscape` / `non_diegetic_music`

与 base 模式定义一致。使用参考音频时，**在匹配可听层的段落里**说明复制/引用关系：

```text
overall_soundscape: The copied ambience layer from <Audio 1> continues throughout the target video.
non_diegetic_music: <Audio 2> is directly reused as the complete audience-only score.
```

完整对白与歌词只写在 `detailed_description` 的 `<d>` 里，**这两段不重复**。

---

## 3. 参考资产硬限制（官方 README）

| 模式 | 图 | 视频 | 音频 | 总文件 | 单段 | 总时长 |
|---|---|---|---|---|---|---|
| **Ref2VA** | ≤ 9 | ≤ 3 | ≤ 3 | ≤ 12 | 2–15 s | ≤ 15 s |
| **FL2VA** | 0 / 1 / 2 | — | — | — | — | — |

输出：**4–15 秒 / 24 FPS / 短边默认 768px / 32kHz 立体声**；
比例 21:9、16:9、4:3、1:1、3:4、**9:16**。

> 官方**没有**给出参考图的分辨率上限、宽高比或格式要求（未找到）。实践规范见 §4。

---

## 4. 设定图实践规范（本项目补充，官方未规定）

### 🔴 设定图分两类，比例不同（官方明文）

官方 `3d-animation-short-generator` 技能原文：**"每张角色卡在可能时为 16:9 生产参考图"**。

| 类型 | 比例 | 用途 | 理由 |
|---|---|---|---|
| **角色卡 / 场景卡** | **16:9** | REF2VA 的 `<Picture N>` 主力，锁定身份与环境 | 要塞下三视图 + 表情 + 道具细节 + 文字标注 |
| **首帧 / 尾帧 / 关键帧** | **= 目标视频比例**（竖屏 9:16） | FL2VA / I2VA / L2VA 的实际画面 | 要当画面用，比例必须对齐否则构图错位 |

**角色卡必含元素（官方清单）**：角色名标注 · 角色定位标注 · **主 3/4 视角** ·
**正/侧/背三视图** · 表情 · 材质/服装/道具细节 · 重要道具标注 · 提示中重复的"**身份锁**" ·
视觉 ID 备注（年龄段/身材/发型/服饰色/签名道具/**不可改特征**）

**场景卡硬性规则**：**只能展示环境，不出现人物、人群、剪影、手、脸或角色客串**。
必含：主环境总览 · 关键光态（日/夜）· 情绪子空间 ·
**连续性地标**（跨镜头保持屏幕位置的固定物体）· 环境中的重要道具

> ⚠️ 官方警告：角色卡锁定后再改，需重做镜头表、分镜、片段、正片与最终合成。
> → 本项目里等于**改一次设定图要全链路重跑**。

| 项 | 规范 | 理由 |
|---|---|---|
| 角色卡尺寸 | `1920×1080`（16:9） | 32 的倍数 |
| 首尾帧尺寸 | `1088×1920`（9:16） | 32 的倍数 |
| **宽高对齐** | **必须是 32 的倍数** | `patch_size(16) × merge_size(2) = 32`，来自 `preprocessor_config.json` |
| 像素范围 | 65,536（256×256）～ 16,777,216（≈4096×4096） | `shortest_edge` / `longest_edge` |
| 单次批量 | **≤ 4 张** | Qwen-Image-2.1 ≤4 张可开 KV cache（3.4× 加速）；10GB 显存约束 |
| 总张数 | 每个主体 ≤ 9（对齐 REF2VA 上限） | |
| 内容分工 | 正面 / 侧面 / 背面 / 服装细节；场景板单独出 | REF2VA 靠多视角锁定身份 |
| 文字 | **字高 ≥ 20px** 才稳定 | Qwen-Image-2.1 实测硬阈值 |
| 背景 | 主体设定图用中性/纯色背景 | 避免背景被误当场景参考 |

### 设定图 → 标签映射

```
Picture 1  角色A 角色卡（16:9，含三视图+标注） → <Subject 1> is the ... in <Picture 1>
Picture 2  角色B 角色卡                        → <Subject 2> is the ... in <Picture 2>
Picture 3  场景卡（纯环境，无人物）             → 单独 <Subject N>，或 storyboard reference
（FL2VA）  Picture 4 首帧（9:16）               → "Picture 4 (from Shot 1) aligns with the 0.00-second mark"
```

> 提示：角色卡一张图里已含正/侧/背三视图，所以**不必**为同一角色出三张独立设定图 ——
> 这能省下 REF2VA 的 9 张配额。

---

## 5. 采样参数（与提示词无关，但同一 job 要用对）

| 参数 | 值 | 说明 |
|---|---|---|
| 采样器 / 调度器 | `res_multistep` / `simple` | 官方推荐；4 步下音质优于 euler |
| shift_video / shift_audio | **12 / 3** | 来自模型定义 |
| CFG | **无** | 走 `BasicGuider`，没有 CFG 概念 |
| denoise | 1.0 | |
| 分辨率（10GB） | `544×960` | 见 `config/registry.yaml` |
| 稀疏注意力 | `sink_conditioning = exact_kv_and_rows` | 保住 reference rows 与音频质量 |

**步数**：融合 turbo 权重 **4**；外挂 turbo LoRA 4–8；非 turbo **20**（漂移则 25）。

> ⚠️ 官方警告原文：*"at 4 steps a reference can end up barely applied, and a subject's pose or
> face angle can drift away from the reference"*
> → `mode=ref2va` 且要求强身份一致时**禁用 4 步**（`build_workflow.py` 已硬校验）。

**负面提示词：官方全文未提及**，且走 `BasicGuider` 无 negative 输入 → **本项目不使用**。

---

## 6. Agent 自检清单

生成后逐条核对：

**结构**
- [ ] Ref2VA 六段式顺序正确？base 模式三段式？
- [ ] 有参考图时，**指令行是第一行**，后面跟**一个空行**？
- [ ] 指令行字面写法与模式匹配（**FL2VA 无尖括号**，I2VA/L2VA 有）？
- [ ] `S.SS` 精确到两位小数？`N` 是实际最后一镜？

**标签**
- [ ] `<Picture N>` / `<Subject N>` / `<Video N>` / `<Audio N>` 各类独立编号、从 1 连续？
- [ ] 仅用于定义角色的图已内联进 `<Subject N>`，没单建 `<Picture N>`？
- [ ] `retention_analysis` 可见内容用 4 种、**音频用另外 4 种**？没混用？
- [ ] `summary` 有方括号任务类型前缀？没引入新标签？
- [ ] `retention_analysis` 里没有 `(Sx)`？

**语言**
- [ ] 全部改写段是英文？仅 `<d>` 与画面内文字保留原语言？
- [ ] `<d>` 内逐字保留原文与标点，没翻译？
- [ ] 画外音用了 `says in an off-screen voiceover` + 声明嘴唇闭合？
- [ ] 画面内文字用英文双引号包裹？

**镜头**
- [ ] `[Shot 1]` 无时间戳，后续 `At MM:SS.mmm` 严格递增且在片长内？
- [ ] 运镜写成句子里的自然英文（不堆标签）？
- [ ] 说话人 ID 跨镜头一致？不发声者无 ID？

**资产与采样**
- [ ] 图 ≤9 / 视频 ≤3 / 音频 ≤3 / 总 ≤12？时长 ≤15s、单段 2–15s？
- [ ] `mode=ref2va` + 强身份一致 → 步数 ≠ 4？
