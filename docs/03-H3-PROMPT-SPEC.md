# 03 — H3 提示词与设定图规范

> **这是 Agent 写提示词时的唯一规范。不按这个写，H3 会明显退化。**
> 来源：MiniMax-AI/MiniMax-H3 官方 README + `skills/h3-prompt-writing/references/ref-en.txt`
> + Comfy-Org 官方教程 + DaSiWa Director 文档。

---

## 1. 两种提示词结构（按模式区分，不能混用）

### A. T2VA / I2VA / FL2VA —— 三段式

```
integrated_multimodal_description: <画面描述，含分镜>
overall_soundscape:               <环境音/音效>
non_diegetic_music:               <配乐>
```

- `non_diegetic_music` 留空时系统自动写 N/A。
- `[Shot 1]` **不带时间戳**；后续镜头写 `[Shot N] At 00:04.500, ...`。
- 在 `[Shot 1]` 之前用 **1–2 句英文先定风格**。
- 生成任务通常 **350–500 英文词**。

### B. REF2VA —— 六段式，**顺序固定，不可打乱**

```
subject_definitions    → 主体定义（人物/物体/场景，绑定参考图）
summary                → 摘要
retention_analysis     → 保留度分析（每个参考被保留到什么程度）
detailed_description   → 分镜详述
overall_soundscape     → 环境音
non_diegetic_music     → 配乐
```

---

## 2. 标签语法（严格）

### 编号体系

| 标签 | 用途 | 独立编号 |
|---|---|---|
| `<Picture N>` | 参考图片 | ✅ 与其它类别互不相干 |
| `<Subject N>` | 主体（人物/物体） | ✅ |
| `<Video N>` | 参考视频 | ✅ |
| `<Audio N>` | 参考音频 | ✅ |

> **各类别独立编号。** `<Picture 1>`、`<Subject 1>`、`<Video 1>` 可以同时存在且互不指代。

### ⚠️ 常见错误写法（官方明确否定）

```
❌ "Picture 1 from Shot 1"        ← 官方指南说没有这种写法
✅ "<Picture 1> (from [Shot 1])"  ← 正确的归属表达
```

### 标准句式

```
# 归属
<Picture 2> is the first frame of [Shot 1], showing ...
the shot begins from <Picture 1>
the shot's keyframe corresponds to <Picture 2>
the shot ends on <Picture 3>

# 时间锚点（官方 H3-Context-IR 输出格式）
For the target video, at 0.00 seconds into the target video,
<Picture 1> (from [Shot 1]) is fully referenced.

# 保留度分析（retention_analysis 段，关系标记只有这四种）
<Picture 2> ([Shot 1] first frame): fully_preserved - <说明>
  关系标记枚举：fully_preserved / partially_preserved / attribute_transfer / weak_reference
```

### 主体绑定（重要）

**如果一张图只是用来定义人物/服装/风格，不要给它建独立的 `<Picture N>` 条目**，
而是**内联进 `<Subject N>`**：

```
✅ <Subject 1> is the young woman in <Picture 1>, wearing ...
❌ <Picture 1> is a portrait of a young woman.  ← 单独建条目会稀释注意力
```

### 对白与转场

```
台词：  <d>[English] 台词内容</d>
说话人： (S1)(S2)
转场：  <scenetrans>
截断：  <cutoff>
```

- 说话人 ID 用 `(S1)(S2)` 标记。
- `<d>` 标签内可保留原语言；**提示词主体一律英文撰写**。

### 语言规则

- **主体必须英文撰写。**
- 只有 `<d>` 内对白/歌词、以及画面内文字（招牌/字卡）保留原语言。
- 官方**没有**给出"中文 vs 英文效果差异"的结论，但规范明确要求英文主体。

---

## 3. 参考资产硬限制

| 模式 | 图 | 视频 | 音频 | 总文件 | 单段时长 | 总时长 |
|---|---|---|---|---|---|---|
| **REF2VA** | ≤ 9 | ≤ 3 | ≤ 3 | ≤ 12 | 2–15 s | ≤ 15 s |
| **FL2VA** | 0 / 1 / 2 | — | — | — | — | — |

输出规格：**4–15 秒 / 24 FPS / 短边默认 768px / 32kHz 立体声**；
比例支持 21:9、16:9、4:3、1:1、3:4、**9:16**。

> 官方**没有**给出参考图的分辨率上限、宽高比或格式要求（未找到）。
> 实践建议见下节。

---

## 4. 设定图实践规范（本项目补充，官方未规定）

由于官方没给设定图规格，这里给出工程上的默认值，**全部落在 `config/registry.yaml`**：

| 项 | 规范 | 理由 |
|---|---|---|
| 长宽比 | **与目标视频一致**（竖屏 9:16 就出竖屏设定图） | 避免裁切导致构图错位 |
| 尺寸 | 9:16 → `1088×1920`（生成）→ 喂入时缩到目标分辨率 | 是 16/32 的倍数，对齐 VAE patchify |
| 单次批量 | **≤ 4 张** | Qwen-Image-2.1 ≤4 张参考可开 KV cache（3.4× 加速）；10GB 卡显存约束 |
| 总张数 | 每个主体 ≤ 9 张（对齐 REF2VA 上限） | |
| 内容分工 | 定妆照（正面/侧面/背面）+ 表情板 + 服装细节 + 场景板 | REF2VA 靠多视角锁定身份 |
| 文字 | **字高 ≥ 20px** 才稳定（Qwen-Image-2.1 实测硬阈值） | 小于 20px 中文会糊 |
| 背景 | 主体设定图用**中性/纯色背景**，场景板单独出 | 避免背景被误当成场景参考 |

### 设定图 → H3 的映射建议

```
Picture 1 = 角色 A 正面定妆照     → <Subject 1> is the ... in <Picture 1>
Picture 2 = 角色 A 侧面定妆照     → 同上，强化 identity
Picture 3 = 角色 A 服装细节       → attribute_transfer
Picture 4 = 场景板                → 单独在 detailed_description 描述
Picture 5 = 首帧（如做 FL2VA）    → <Picture 5> is the first frame of [Shot 1]
```

---

## 5. 采样参数配方

### 通用

| 参数 | 值 | 说明 |
|---|---|---|
| 采样器 | `res_multistep` | 官方推荐；MATLOWAI 实测 **4 步下音质优于 euler** |
| 调度器 | `simple` | |
| **shift_video** | **12** | 来自模型定义 |
| **shift_audio** | **3** | 来自模型定义 |
| CFG | **无** | 走 `BasicGuider`，没有 CFG 概念。别硬塞 CFG 节点 |
| denoise | 1.0 | |
| 分辨率（10GB） | `544×960` | 见 `config/registry.yaml` 档位表 |

### 步数

| 场景 | 步数 | 说明 |
|---|---|---|
| 融合 turbo 权重 | **4** | MATLOWAI 原话 "run it at 4 steps" |
| 外挂 turbo LoRA | 4 或 8 | |
| 非 turbo（质量优先） | 20（漂移则 25） | 官方默认 |
| REF2VA + turbo | 4 | ⚠️ 见下方警告 |

### ⚠️ 官方明确警告

> *"at 4 steps a reference can end up barely applied, and a subject's pose or face angle can drift away from the reference"*

**翻译：需要紧密跟随设定图时，不要开 4 步 turbo。** 参考会被弱化，人物姿势/脸的角度会漂。

**本项目处置：**
- `turbo=fused` 且 `mode=ref2va` 且**要求强身份一致** → **强制 8 步或 20 步**，不允许 4 步。
  这条规则已写进 `comfy/build_workflow.py` 的校验逻辑。
- 纯氛围/转场/远景镜头可以用 4 步。

### 稀疏注意力

保持 **`sink_conditioning = exact_kv_and_rows`**（H3 专用），以保住 reference rows 与音频质量。

---

## 6. 负面提示词

> **官方 README 与提示词指南均未提及负面提示词（未找到）。**
> ComfyUI 的 H3 链路走 `BasicGuider`，没有 negative conditioning 输入。
> **本项目不使用负面提示词。** 想规避的内容直接写进 `detailed_description` 的排除描述里。

---

## 7. 提示词长度

官方未给上限（未找到）。参考 token 用量示例：T2VA 8565 / I2VA 22822 / REF2VA 39299（非上限）。
实践建议：**350–500 英文词**为主体，REF2VA 因六段式会更长，属正常。

---

## 8. Agent 写提示词的检查清单

生成 H3 prompt 后，逐条自检：

- [ ] 模式匹配：REF2VA 用六段式且顺序正确？T2VA/FL2VA 用三段式？
- [ ] `<Picture N>` / `<Subject N>` 编号各自独立、从 1 连续？
- [ ] 没有出现 `Picture 1 from Shot 1` 这种错误写法？
- [ ] 只用于定义主体的图已内联进 `<Subject N>`，没有单独建 `<Picture N>`？
- [ ] `retention_analysis` 的关系标记只用四种枚举之一？
- [ ] 对白用 `<d>` 包裹、说话人用 `(S1)(S2)`？
- [ ] 主体是英文？仅 `<d>` 和画面内文字保留原语言？
- [ ] 参考资产数量：图 ≤9、视频 ≤3、音频 ≤3、总 ≤12？
- [ ] 时长 ≤15 秒？单段参考 2–15 秒？
- [ ] 若 `mode=ref2va` 且要求强身份一致 → 步数 ≠ 4？
- [ ] `[Shot 1]` 不带时间戳，后续 `[Shot N] At 00:0X.XXX`？

---

## 9. 参考：官方示例（可直接复用为 few-shot）

```
integrated_multimodal_description:
[Shot 1] A lone astronaut floats above a neon-lit cyberpunk cityscape at night.
Rain streaks across their visor reflecting holographic billboards and flying vehicles below.
[Shot 2] At 00:03.000 the camera pushes in slowly toward the visor as a massive digital
dragon hologram rises through the clouds behind them, illuminating the scene in pulses of crimson light.

overall_soundscape: Distant rain on metal, faint city hum, synthetic wind, low ambient synth pad underneath.
non_diegetic_music: Pulsing dark synthwave beat enters at 00:02.000, crescendo when the dragon appears, holding until end.
```

```
# FL2VA 首尾帧
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns
with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the
8.00-second mark of the target video.

integrated_multimodal_description:
[Shot 1] The dusty desert road stretches empty under a blazing midday sun, heat haze shimmering.
[Shot 2] At 00:02.000 a vintage red convertible crests the horizon and accelerates toward camera.
...
```
