# 02 — 模型选型结论与决策依据

> 所有结论均基于 2026-10-05 的实测调研，出处见 [docs/07-SOURCES.md](07-SOURCES.md)。

---

## 1. MiniMax-H3 是什么（先对齐认知）

| 项 | 事实 |
|---|---|
| 架构 | **H3-Omni-Transformer：33B dense、单流 Transformer**（非双流、非 U-Net），AdaLN 调制，三维 MM-RoPE (t,h,w) |
| 联合输出 | **video latent + audio latent 一起预测**（这是 H3 最大的特点） |
| 编码器 | H3-Encoder 基于 **Qwen3-VL-32B 全量权重，取第 50 层 hidden states**；tokenizer 必须用仓库自带版本（新增 `<d>` 等 token） |
| VAE | H3-VisualVAE = `f16t4d24`（空间 16×、时间 4×、24 latent channels），进 Transformer 前 `1×2×2` patchify → 有效空间 32×、时间 4× |
| 输出 | 4–15 秒、24 FPS、短边默认 768px、32kHz 立体声；比例 21:9/16:9/4:3/1:1/3:4/9:16 |
| 变体 | 实际发布 **两个 task checkpoint**：`FL2VA` 与 `Ref2VA` |
| ComfyUI | **原生支持，不需要插件** |

### 变体命名澄清

| 缩写 | 含义 | 输入图数量 |
|---|---|---|
| **T2VA** | Text-to-Video-Audio | 0 张 |
| **I2VA** | Image(首帧)-to-Video-Audio | 1 张 |
| **FL2VA** | First/Last-frame-to-Video-Audio | 0 / 1 / 2 张（0 即 T2VA） |
| **R2VA / Ref2VA** | Reference-to-Video-Audio（omni-reference） | 图 ≤9 + 视频 ≤3 + 音频 ≤3，总文件 ≤12 |

> ⚠️ **"FLF2VA" 这个写法在官方 README 里并不存在**，它就是 FL2VA 的首尾帧用法。

---

## 2. ★ H3 主权重：选原版还是三个微调整合模型？

### 决策表

| 候选 | 体积 | 类型 | 模式覆盖 | turbo | 10GB 可用 | 定位 |
|---|---|---|---|---|---|---|
| **DaSiWa Hybrid Turbo v3 int4** | 12.25 GB | hybrid | T2VA/I2VA/L2VA/FL2VA/REF2VA | 已融合 | ✅ | **10GB 主力** |
| **Singularity Pruned w4a8** | 11.8 GB | 微调融合 | T2VA/I2VA/REF2VA/V2VA | 需外挂 | ✅ | **10GB hero shot / 人物特写** |
| DaSiWa Hybrid Turbo v3 int8 | 20.48 GB | hybrid | 同上 | 已融合 | ⚠️ 慢 | 16GB+ 主力 |
| MATLOWAI fused-turbo-int8-convrot | 21 GB | fused | T2VA/I2VA/FL2VA/REF2VA | 已融合 | ⚠️ 慢 | 16GB+ 备选 |
| Singularity Pruned int8 | 21 GB | 微调融合 | REF2VA 等 | 需外挂 | ❌ | 24GB+ |
| 原版 int8_convrot (fl2va / ref2va) | 各 ~20 GB | 官方 | 各管一半，需换文件 | 需外挂 | ❌ | **仅作 A/B 基线** |

### 结论

**不要用原版。** 理由是工程性的，不是质量性的：

> 原版把 FL2VA 与 Ref2VA 做成**两个独立的 ~20GB 文件**。
> 你的生产线要在这两种模式之间反复切换（设定图驱动走 REF2VA，纯文本镜头走 T2VA/FL2VA），
> 原版意味着每次切换都要重新加载 20GB 权重 —— 在 10GB 卡上这是灾难。

**hybrid / fused 是唯一现实的选择**：一个文件同时支持两种模式。

### 三个微调整合模型的差异

**① MATLOWAI `minimax-h3-fused-turbo-int8-convrot`（你已下载 21GB）**
- "fused" = 三层融合：
  1. 底座是 pruned `fl2va`，用 **rank-1024 SVD 把 (ref2va − fl2va) 权重 delta 融进去** → 一个文件双模式
  2. 融入 **lightx2v FL2VA Turbo 8-step v1.0 @1.0**（rank-24 resize）
  3. 融入 **Mystic v2.0 @0.7**（运动平滑）
- "int8_convrot" = 融合后一次性量化，50 个 block 里四个重 Linear（`qkv_proj`/`out_proj`/`fc1`/`fc2`）转 INT8，其余保持 BF16/F32，**ComfyUI 原生 `comfy_quant` 布局 → 直接 `UNETLoader`，不需要自定义 loader**
- 作者原话：**"it is a 4-or-8 NFE model: run it at 4 steps"**
- 实测：RTX PRO 6000 96GB 上 4 步 76s / 8 步 103s；**16GB 卡峰值 11.0GiB、65s**
- ⚠️ 风险：**r1024 SVD 是对 (ref2va − fl2va) 差值的低秩近似**，ref2va 能力是"近似还原"，不是原生。人物一致性要求高时要 A/B 验证。

**② Singularity（HuggingFace WarmBloodAban）**
- **不是 LoRA，是融合多个 checkpoint（ref / fl / b25-49）+ 深度高步数微调后的完整权重**，再用 3 天做剪枝消除高步数训练伪影
- 卖点（都有明确针对性）：
  - HDR 画质、去运动模糊
  - **远景人脸修复**（中远景不崩脸）← H3 原版最大痛点
  - 去油光去塑料感
  - 武打/冷兵器/奇幻 VFX
  - **100% 保留原模型 prompt adherence**
- 三档：int8 34GB / pruned int8 21GB / **pruned w4a8 11.8GB**
- 作者推荐搭配 `minimax_h3_ref2v_turbo_4step_v0.1`（4 步）
- ⚠️ README **未给出 steps/cfg/sampler/分辨率/显存**，需自行试。用本仓库默认：`res_multistep` / `simple` / shift 12 / audio 3

**③ DaSiWa Hybrid Turbo v3（Civitai 2877206）**
- "ref2va" = 面向 Ref2VA 任务分支；**"hybrid" = REF2VA + FL2VA 双兼容**
- 7 个版本：Hybrid v1/v2/v3、Hybrid Turbo v1/v2/v3、Hybrid 8Turbo v1、Hybrid 4Turbo v1
- Turbo v3 文件：int8 20.48GB + int4 12.25GB
- 作者推荐：**Turbo（蒸馏）用 `euler/simple` 或 `LCM/simple`，Shift Video 6–12、Shift Audio 3–5，4 或 8 步**
  （注意：作者示例工作流实际用 shift 12/3，与文档 6–8/4–5 不一致，**以 A/B 实测为准**）
- ★ **最大工程优势：与 `ComfyUI-DaSiWa-Nodes` 的 `MiniMaxH3Director` 同源。** Director 一个节点把
  T2VA/I2VA/L2VA/FL2VA/REF2VA/Inpaint 全部模式暴露成**一个 `mode` 输入**，Agent 改一个字符串就能切模式，
  不用换整张图。这对自动化是决定性的。

### 最终推荐（按场景）

```
默认生产线        → DaSiWa Hybrid Turbo v3 int4（12.25GB）+ euler/simple 4 步
人物特写/hero shot → Singularity Pruned w4a8（11.8GB）+ res_multistep/simple 20 步（或外挂 turbo 4 步）
16GB+ 机器        → MATLOWAI fused turbo（21GB）+ res_multistep/simple 4 步
A/B 质量基线      → 原版 int8_convrot + 官方 turbo LoRA，20 步
```

---

## 3. ★ 设定图模型：Krea-2 还是 Qwen-Image-2.1？

### 直接结论

> **设定图用 Qwen-Image-2.1 原版（int8_convrot）。**
> **Krea 2 不做设定图，只做风格板/封面。**

### 决定性理由

Krea 2 官方技术报告把 **「通用图像编辑」与「通用 image reference」都列为未来工作**，
当前只支持 **风格参考（style reference）**。也就是说：

> **Krea 2 根本做不了"同一角色换姿势/换场景"的参考图。**
> 而 H3 的 REF2VA 恰恰就是要吃同一角色的多张设定图（最多 9 张）。

这是一票否决项，不是"谁更好"的问题。

### 逐项对比

| 维度 | Qwen-Image-2.1 | Krea 2 | 胜 |
|---|---|---|---|
| 多图参考 / 身份一致 | **最多 10 张参考图**，实测双人合图两个身份都保住、换装换场景"脸还是同一个人" | 仅风格参考 | **Qwen** |
| 中英文文字渲染 | 三级字号中文海报零错字，**字高 ≥20px 稳定**；中英混排/竖排/公式/UI 基本全对 | 仅为 RL 奖励之一，无量化分数，中文需社区 CN LoRA | **Qwen** |
| 原生分辨率 | **2K**，官方含 9:16 = 1536×2752 | 训练上限 1024px，**无原生 2K** | **Qwen** |
| 复杂分镜提示词遵从 | 8B 编码器，计数/方位/属性绑定/复合关系实测全对，多格分镜同人同服 | 4B 编码器（ComfyUI 版） | **Qwen** |
| 单张美学 | 改进排版/人像光照/细节 | **AA 榜全球前十、独立实验室第 2**，RAW 未蒸馏可塑性强 | **Krea** |
| 速度 | 40 步（可压到 25；Viggle 蒸馏 5 步） | **Turbo 8 步 CFG 0** | **Krea** |
| 量化/加速生态 | int8_convrot / GGUF / PE / ControlNet 齐全 | 量化生态未找到 | **Qwen** |
| 许可证 | ⚠️ **Research License，仅非商用** | 年营收 <$1M 可免费商用 | **Krea** |

### 原版还是微调版？

**Qwen-Image-2.1 → 用原版。**

理由：设定图的核心诉求是**身份一致 + 文字准确**，任何风格化社区 checkpoint 都会损伤这两项。

- 主用：`qwen_image_2.1_int8_convrot.safetensors`（7.26GB；bf16 是 14.2GB）
- 参数：25 步 / cfg 1 / euler / simple（`cfg 1` 时负向提示无效，这是官方行为）
- 可选加速：**Viggle Turbo v0.2**（DMD 蒸馏 5 步 rank-256 LoRA）做**草稿/预筛**，提速 8×。
  ⚠️ 但它"小字与长文本更易乱码、编辑仅支持 ≤3 张参考图"，**正片设定图必须回到原版 25–40 步**。
- 低显存走**官方 int8_convrot**，不要走 GGUF（需 leejet fork 的 ComfyUI-GGUF，且走较慢的内存路径）。
- 10GB 卡上 10 张参考图需 `use_kv_cache=False`（38.4GB / 190s 那档是 48G 卡数据）；
  ≤4 张参考开 KV cache 有 3.4× 加速，但每张条件图多吃 ~2GB。
  **10GB 档位建议单批 ≤4 张设定图。**

**Krea 2 → 用官方 Turbo 原版（8 步 / CFG 0 / mu 1.15）。** RAW 仅在你要训练自有风格 LoRA 时用
（官方原则："TRAIN on Raw and RUN on Turbo"）。

**不要用 DaSiWa 的 Krea2 微调版做设定图：**
1. 取向是 Unchained / NSFW / 强风格化（DarkDesire "Touched by Darkness"、CuteDisaster、MirroredSkies），与中性设定图冲突
2. 体积 13–25GB，且推荐 CFG 1 与官方 Turbo 的 CFG 0 不一致，要重新调参
3. **它不补上 Krea 2 缺失的 identity 参考能力** —— 换它解决不了根本问题

> 你本地已下载 `DasiwaKrea2TurboRaw_darkdesireV3TurboUC_int4/int8`。
> 定位：**特定题材（暗黑/奇幻）短片的美学引擎 + 封面海报**，不进设定图链路。

### ⚠️ 唯一可能反转的因素：许可证

如果项目**商用**：Qwen-Image-2.1 需向 Qwen 取得商用授权，否则合规替代是 **Apache-2.0 的 Qwen-Image-Edit-2509**
（其多图参考上限尚未验证，需实测）。这是整条线唯一的硬合规风险点。

---

## 4. VAE 选型

| VAE | 体积 | 解码耗时（10.1s / 243f） | 画质 |
|---|---|---|---|
| 官方 fp16 | 5.21 GB | 17.0 s（ComfyUI 0.36） | 基准 |
| 官方 int8_convrot | 2.81 GB | **10.0 s** | 差 1.2–1.3/255 灰阶，PSNR 42.1–43.0 dB，SSIM 0.983–0.988 |
| **lynnreal light int8_convrot** | **2.14 GB** | **再快 1.3×** | 同上量级 |

**结论：无条件上 int8_convrot 系。** 画质代价可忽略（PSNR 42dB+），速度收益巨大。
t10 档位直接用 **`minimax_h3_lynnreal_light_vae_int8_convrot`**（2.14GB，Kijai 对
`stdstu123/LynnReal-Onmi-light-vae` 的 int8-convrot 量化版）。

音频 VAE 用 **`minimax_h3_audio_vae_fp32.safetensors`**（605MB），**REF2VA 必需**。

⚠️ int8_convrot VAE 的提速需要 **ComfyUI ≥ 0.36.0**。

---

## 5. 目录放置（照抄）

```
models/
├── diffusion_models/
│   └── MiniMaxH3/
│       ├── dasiwa_minimax_h3_ref2va_v3_pruned_hybrid_turbo_int4.safetensors      ← 10GB 主力
│       ├── Minimax-h3_Singularity_ref2va_v1.3_Pruned_w4a8.safetensors            ← hero shot
│       ├── minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors  ← 16GB+ 主力
│       └── minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors                ← 待测
├── text_encoders/
│   └── qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors        ← 15.7GB（不需要 Blackwell）
├── vae/
│   ├── minimax_h3_lynnreal_light_vae_int8_convrot.safetensors
│   ├── minimax_h3_video_vae_int8_convrot.safetensors       ← 备
│   ├── minimax_h3_audio_vae_fp32.safetensors               ← REF2VA 必需
│   └── taeh3.safetensors                                    ← 预览
├── loras/
│   ├── minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
│   └── minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors
├── diffusion_models/   ← Qwen-Image-2.1（注意不要放 MiniMaxH3 子目录）
│   └── qwen_image_2.1_int8_convrot.safetensors
└── text_encoders/
    └── qwen3vl_8b_int8_convrot.safetensors
```
