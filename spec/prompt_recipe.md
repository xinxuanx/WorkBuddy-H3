# 提示词配方（可复用骨架）

> `prompt.from_shotlist()` 的模板来源。Agent 不要自己发明结构，套这里。
> **逐字照抄的指令行必须照抄**，不能改写。
> 冲突时以 `spec/official/h3-prompt-writing/references/*.txt` 原文为准。

---

## 0. 指令行速查（逐字照抄）

| 模式 | 指令行（第一行，后跟空行） |
|---|---|
| T2VA | *（无）* |
| I2VA | `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` |
| FL2VA | `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.` |
| L2VA | `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.` |

🔴 FL2VA **不带尖括号**（`Picture 1 (from Shot 1)`），I2VA/L2VA **带尖括号**（`<Picture 1> (from [Shot 1])`）。

---

## A. Base 模式骨架

```
{{INSTRUCTION_LINE}}

integrated_multimodal_description: [Shot 1] {{style}}, {{composition}}...
[Shot 2] At {{MM}}:{{SS}}.{{mmm}}, {{...}}

overall_soundscape: {{1-4 句英文}}
non_diegetic_music: {{1-3 句英文，或 N/A}}
```

- 无图时**不写指令行**，直接从 `integrated_multimodal_description:` 开始
- 风格写在 `[Shot 1]` **之后**
- `[Shot 1]` 不带时间戳

### 分模式写法

```
# I2VA —— 首帧锚点 → 动作起始 → 持续发展 → 结果/反应
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, the young woman shown in <Picture 1> remains beside the rain-covered train window, preserving her appearance, clothing, seat position, and the carriage layout. The camera trucks right with small amplitude at slow speed as she lifts her gaze...

# FL2VA —— 首帧状态 → 可见中间变化 → 差异逐步收窄 → 尾帧状态（官方倾向单镜）
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, ...begins in the position and framing established by Picture 1... settles into the pose, spacing, and composition established by Picture 2 at the end of the shot.

# L2VA —— 合理前置状态 → 明确动作与过渡 → 最后一镜逐步收敛 → 尾帧落地
How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the 6.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, a close shot begins with an intact drinking glass near the edge of a dark wooden table, while the same hand and sleeve visible in <Picture 1> approach from the right... settle into the exact broken arrangement, hand position, camera angle, lighting, and final composition established by <Picture 1>.
```

---

## B. Ref2VA 骨架（六段式，顺序固定）

```
subject_definitions:
<Subject 1> is {{name}}, {{appearance}}, as seen in <Picture 1>.
<Subject 2> is {{scene/env}}, as seen in <Picture 4>.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[{{task_type}}] {{一句话概括目标视频与主要参考关系}}

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - {{说明}}
<Picture 2> ([Shot 1] first frame): fully_preserved - {{说明}}
<Picture 3> (costume detail): attribute_transfer - {{说明}}
<Audio 1>: reference - {{说明}}

detailed_description:
{{1-2 句英文定风格，在 [Shot 1] 之前}}
[Shot 1] {{composition, subject, action, camera, sound}}
[Shot 2] At 00:03.000, {{...}}
<Subject 1> (S1) says: <d>[English] {{台词}}</d>

overall_soundscape: {{1-4 句英文}}
non_diegetic_music: {{1-3 句英文，或 N/A}}
```

### 任务类型前缀（`summary` 必填）

`keyframe completion` · `reference generation` · `video editing` ·
`video continuation` · `audio reuse` · `audio reference`
（多选时用 ` + ` 连接，不重复）

### retention 两套标记（🔴 别混用）

| 可见内容（Subject/Picture/Video） | 音频（Audio） |
|---|---|
| `fully_preserved` | `fully_copy` |
| `partially_preserved` | `partially_copy` |
| `attribute_transfer` | `reference` |
| `weak_reference` | `weak_reference` |

---

## C. 标签与写法速查

| 元素 | 写法 |
|---|---|
| 参考图（帧锚点/构图锚点） | `<Picture N>` |
| 可复用可见内容 | `<Subject N>` |
| 参考视频（整片结构/剪辑源） | `<Video N>` |
| 音频 | `<Audio N>` |
| 对白/歌词 | `<d>[English] {{原文}}</d>` |
| 说话人 | `(S1)`；多人同说 `(S1,S2)` |
| 主体 + 说话人同时 | `<Subject 2> (S1) turns and says, <d>[English] ...</d>` |
| 画外音 | `says in an off-screen voiceover` + **`while his lips remain completely closed`** |
| 对白跨剪切 | 两段连接处各用 `<scenetrans>` + 说明声音跨镜连续 |
| 片尾截断 | `<cutoff>` |
| 听不清 | `[unclear]`（不要猜） |
| 画面内文字 | 英文双引号：`A red neon sign reading "营业中" glows...` |
| 帧锚点自然写法 | `the shot begins from <Picture 1>` / `the shot's keyframe corresponds to <Picture 2>` / `the shot ends on <Picture 3>` |

### 运镜（类型 + 幅度 + 速度，写进句子）

```
The camera pushes in with small amplitude at slow speed toward the folded letter in her hands.
The camera pans right with large amplitude at fast speed, revealing the open doorway.
The camera holds a static shot as the runner exits the frame.
```

### 剪切动词

`the camera cuts to` / `the shot cuts to` / `the shot transitions to` /
`the shot changes to` / `the shot switches to`

---

## D. 设定图提示词骨架（给 Qwen-Image-2.1）

```
# 正面
{{name}}, {{appearance}}, front view, full body, neutral light grey background,
even studio lighting, sharp focus, high detail, 9:16 vertical

# 侧面
{{name}}, {{appearance}}, side profile view, full body, neutral light grey background, ...

# 背面
{{name}}, {{appearance}}, back view, full body, neutral light grey background, ...

# 服装细节
{{costume}}, flat lay detail, fabric texture visible, neutral background, ...

# 场景板（不含人物）
{{scene}}, establishing wide shot, cinematic lighting, no people, 9:16 vertical
```

- 中性/纯色背景（主体图），场景板单独出
- 画面内文字 **字高 ≥ 20px**
- 一次 ≤ 4 张（10GB 档位可开 KV cache）
- 长宽比 = 目标视频长宽比

---

## E. 常见错误 → 修正

| 错误 | 修正 |
|---|---|
| FL2VA 写成 `<Picture 1> (from [Shot 1])` | FL2VA 裸写：`Picture 1 (from Shot 1)` |
| 指令行放在字段之后 / 没空行 | 指令行必须**第一行**，后跟**一个空行** |
| 漏 L2VA（尾帧模式） | L2VA = 反推前置状态 → 收敛到尾帧 |
| 音频用了 `fully_preserved` | 音频用 `fully_copy` / `partially_copy` / `reference` / `weak_reference` |
| `summary` 没有任务类型前缀 | 必须 `[reference generation]` 之类开头 |
| `retention_analysis` 里写了 `(S1)` | 该段不写 `(Sx)` |
| 画外音没声明嘴唇闭合 | 必须 `while his lips remain completely closed` |
| 运镜在句末堆标签 | 写成句子里的自然英文 |
| 画面内文字没加双引号 | 用英文双引号包裹，保留原语言 |
| 角色能听到的音乐写进 `non_diegetic_music` | 那是 diegetic，写进主描述段 |
| `overall_soundscape` 随便写 N/A | 仅**明确全片静音**时才用 N/A |
| 参考图 10 张 | ≤ 9 |
| ref2va 强身份却 4 步 | ≥ 8 步 |
