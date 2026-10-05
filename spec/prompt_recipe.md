# 提示词配方（可复用骨架）

> `prompt.from_shotlist()` 的模板来源。Agent 不要自己发明结构，套这里。

---

## A. T2VA / I2VA / FL2VA（三段式）

```
integrated_multimodal_description:
{{style_bible}}

[Shot 1] {{shot1_description}}
[Shot 2] At {{mm}}:{{ss}}.{{ms}}, {{shot2_description}}
...

overall_soundscape: {{soundscape}}
non_diegetic_music: {{music}}
```

规则：
- `{{style_bible}}` = 1–2 句英文定风格，放在 `[Shot 1]` 之前
- `[Shot 1]` **不带时间戳**；后续 `[Shot N] At 00:04.500, ...`
- 单镜头时整段不分镜也行
- 主体 350–500 英文词

---

## B. REF2VA（六段式，顺序固定）

```
subject_definitions:
<Subject 1> is {{name}}, {{appearance}}, as seen in <Picture 1>.
<Subject 2> is ...

summary:
{{一段话概括整个片段}}

retention_analysis:
<Picture 1> ({{subject}} front view): fully_preserved - {{说明}}
<Picture 2> ({{subject}} side view): fully_preserved - {{说明}}
<Picture 3> ({{subject}} costume detail): attribute_transfer - {{说明}}
<Picture 4> (scene board): partially_preserved - {{说明}}

detailed_description:
[Shot 1] {{描述}}
[Shot 2] At 00:03.000, {{描述}}
<d>[English] {{台词}}</d> (S1)
<scenetrans>

overall_soundscape: {{soundscape}}
non_diegetic_music: {{music}}
```

### retention_analysis 的四种枚举（只能用这四种）

| 标记 | 含义 |
|---|---|
| `fully_preserved` | 完全保留（脸、服装、姿态都对上） |
| `partially_preserved` | 部分保留（保留部分特征） |
| `attribute_transfer` | 属性迁移（只要服装/色调/材质，不要脸和姿态） |
| `weak_reference` | 弱参考（仅氛围参考） |

---

## C. 标签速查

| 标签 | 用法 |
|---|---|
| `<Picture N>` | 参考图，**与其它类别独立编号** |
| `<Subject N>` | 主体（人物/物体） |
| `<Video N>` | 参考视频 |
| `<Audio N>` | 参考音频 |
| `<d>[English] 台词</d>` | 对白 |
| `(S1)(S2)` | 说话人 ID |
| `<scenetrans>` | 转场 |
| `<cutoff>` | 截断 |
| `[Shot N] At 00:0X.XXX` | 分镜时间戳 |

### 归属写法

```
✅ <Picture 2> is the first frame of [Shot 1], showing ...
✅ the shot begins from <Picture 1>
✅ the shot's keyframe corresponds to <Picture 2>
✅ the shot ends on <Picture 3>
✅ <Picture 1> (from [Shot 1]) is fully referenced
❌ Picture 1 from Shot 1            ← 官方明确否定
```

---

## D. 设定图提示词骨架（给 Qwen-Image-2.1）

```
# 角色定妆照（正面）
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

要点：
- **中性/纯色背景**（主体设定图），场景板单独出 —— 否则背景会被当成场景参考
- 画面内文字 **字高 ≥ 20px**
- 一次 ≤ 4 张（10GB 档位可开 KV cache）
- 长宽比 = 目标视频长宽比

---

## E. 常见错误 → 修正

| 错误 | 修正 |
|---|---|
| `Picture 1 from Shot 1` | `<Picture 1> (from [Shot 1])` |
| 给"定义人物的图"单独建 `<Picture N>` | 内联进 `<Subject N>` |
| `[Shot 1] At 00:00.000` | `[Shot 1]`（首镜不带时间戳） |
| 主体写中文 | 主体英文，仅 `<d>` 与画面内文字保留原语言 |
| retention 用 `mostly_preserved` | 只用四种枚举 |
| 参考图 10 张 | ≤ 9 |
| ref2va 强身份却 4 步 | ≥ 8 步 |
