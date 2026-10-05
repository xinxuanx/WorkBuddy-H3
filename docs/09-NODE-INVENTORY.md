# 09 — 实测节点清单（从你本地可跑的工作流提取）

> 来源：`F:\H3\MiniMax-H3一键短剧V7.5_Singularity_PDMD_LynnReal_SOP.json`（238 节点，69 种类型）
> 与 `workflow_nodes_summary.json`（DaSiWa V7.5 SOP）。
> **这些节点名是实测的，不是猜的。** 优先于任何文档里的猜测。

---

## 1. 核心生成链路

| 节点类型 | 实测输入 | 实测取值 | 说明 |
|---|---|---|---|
| **`UNETLoader`** | `unet_name`, `weight_dtype` | `Minimax-h3_Singularity_ref2va_Pruned_v1.3_int8.safetensors`, `default` | 主权重 |
| **`CLIPLoader`** | `clip_name`, `type`, `device` | `qwen3vl_32b_minimax_h3_int8_convrot.safetensors`, **`minimax`**, `default` | ★ **`type` 是 `minimax`，不是 `qwen3_vl`** |
| **`VAELoader`**（视频） | `vae_name` | `minimax_h3_lynnreal_light_vae_int8_convrot.safetensors` | ★ **你已在用 lynnreal light VAE** |
| **`VAELoader`**（音频） | `vae_name` | `minimax_h3_audio_vae_fp32.safetensors` | REF2VA 必需 |
| **`Yuan_MiniMaxH3Video`** | `clip`, `vae`, `audio_vae`, `ref_images`, `ref_video_1`, `ref_video_audio_1`, `ref_audio_1`, `mode`, `prompt`, `width`, `height`, `length`, `ref_image_size`, `guide_frame_idx` | mode=`参考图生视频`, 512×512, length=124, ref_image_size=`匹配` | 输出 `正向`(CONDITIONING) + `潜在空间`(LATENT) |
| **`MiniMaxH3HybridLoader`** | `base_model`, `overlay_model`, `overlay_preset`, `block_range_start`, `block_range_end`, `final_adaln_from_overlay`, `custom_overlays`, `custom_base`, `weight_dtype` | base=`minimax_h3_fl2va_pruned_int8_convrot`, overlay=`minimax_h3_ref2va_pruned_int8_convrot`, preset=`block_range_adaln`, **25→49** | ★ **这就是你本地 `b25-49` 权重的由来** |
| **`MiniMaxH3TurboSampler`** | — | — | 备用 turbo 采样器 |
| **`H3AspectResolution`** | `megapixels`, `aspect_ratio`, `multiple` | `16:9 横屏`, `16` | 输出 width/height/aspect_ratio/report |
| **`H3StreamedBlocks`** | `model`, `q_chunk`, `kv_chunk`, `mlp_chunk`, `min_tokens`, `kv_block`, `final_layer_chunk`, `final_layer_gemm`, `kv_store`, `trim_forward`, `self_check`, `exact_av_rows` | 16GB 档：`16384, 16384, 16384, 32768, 0, 16384, 'exact (whole GEMM, one fp32 buffer)', 'bf16 (exact)', True, False, False` | ★ **低显存关键：分块推理** |

`Yuan_MiniMaxH3Video` 的 `mode` 下拉是**中文**：
`纯文生视频` / `首帧图生视频` / `尾帧图生视频` / `首尾帧生视频` / `参考图生视频`

---

## 2. H3 专用辅助节点

| 节点 | 作用 |
|---|---|
| `H3EvictTextEncoder` | 编码完卸载 text encoder（**低显存必备**） |
| `H3FreeCache` | 释放缓存 |
| `H3InjectVideoLatent` | 注入视频 latent |
| `H3PerFrameDenoise` | 逐帧降噪（配合人脸尺寸：`face_px_small=30`, `face_px_large=120`, `denoise_multiplier_small_face=0.8`, `denoise_multiplier_large_face=0.35`, `scale_mode=absolute_px`, `gamma=1`, `smooth_frames=9`） |
| `H3FaceTrackCrop` / `H3FaceStitch` | 人脸追踪裁切 + 缝合（修脸） |
| `H3NativeAudioLock` | 音频锁定 |
| `H3V64TrackedSave` / `H3V65ReferenceAudit` / `H3V64ApprovedMerge` | 参考审计与批准合并 |

## 3. 续接（Continuity）

| 节点 |
|---|
| `MiniMaxH3MotionContext_ContinuityGuard` |
| `MiniMaxH3MotionContextSaveLatent` / `MiniMaxH3MotionContextLoadLatent` |
| `MiniMaxH3MotionContextTrim_ContinuityGuard` |
| `Yuan_MiniMaxH3Video_ContinuityGuard` |

## 4. 采样链路（实测）

| 节点 | 实测取值 |
|---|---|
| `KSamplerSelect` | `euler`（主） / `er_sde`（人脸细化） |
| `BasicScheduler` | `simple`, steps=4, denoise=0.45（人脸细化档） |
| **`ManualSigmas`** | **6 步**：`1.0000, 0.9730, 0.9231, 0.7500, 0.5500, 0.3014, 0.0000`<br>**8 步（备用）**：`1.0000, 0.9882, 0.9730, 0.9524, 0.9231, 0.8780, 0.5500, 0.3014, 0.0000` |
| `BasicGuider` | model + conditioning（**无 CFG**） |
| `SamplerCustomAdvanced` | guider + sampler + sigmas + latent + noise |
| `RandomNoise` | `noise_seed` |

> ⚠️ 实测工作流用 `ManualSigmas` 手写 sigma 序列，而不是 `BasicScheduler` 自动算。
> 6 步与 8 步的 sigma 表已记录在上面，**可直接复用**。

## 5. DaSiWa 节点包（`ComfyUI-DaSiWa-Nodes`）

已在压缩包中确认源码文件：
`nodes/helper_minimax_h3_director.py`、`nodes/helper_minimax_h3_prompt_builder.py`、
`nodes/h3_continuity/*`、`nodes/h3_forge.py`、`nodes/helper_refmod_format.py` …

| 节点 | 作用 |
|---|---|
| **`MiniMaxH3Director`** | ★ 一站式指挥台。T2VA/I2VA/L2VA/FL2VA/REF2VA/Inpaint 全模式一个节点，REF2VA = 9图+3视频+3音频，单段 2–15s，frame_rate 默认 24，Auto 分辨率 = 短边 768 |
| `DaSiWa_SeedControl` | 完整 64-bit 种子（匹配 H3 种子空间） |
| `DaSiWa_NodeStatusSwitch` | 单开关 mute/bypass 任意节点，最多 99 槽 |
| `DaSiWa_LTX2LoraLoader` | 10 插槽 LoRA 堆叠，强度 −5.0~+5.0；**H3 用 Basic 模式** |
| `DaSiWa_MetadataImageSaver` | 嵌 A1111 风格元数据 |
| `DaSiWa_EnhancedVideoCombine` | PyAV 编码，可拖预览，可导出首尾帧 |
| `DaSiWaH3ContinuityPublish` | 从固定 latent 检查点延长镜头；检查点在 `output/df_h3_continuity/` |

## 6. 其它出现频次高的辅助节点

`RegexExtract`(28) · `GetNode`(26) · `SetNode`(22) · `ComfySwitchNode`(17) ·
`FxAiTextPreview`(14) · `PrimitiveStringMultiline`(10) · `ComfyMathExpression`(9) ·
`YUAN_TXT*`(约 20) · `MultiImageLoader`(3) · `easy forLoopStart/End` ·
`easy cleanGpuUsed` · `FxAiReleaseResources` · `AudioMerge` · `VAEDecode` · `PreviewImage`

---

## 7. 对本项目模板的影响

`comfy/templates/h3_core.json` 已按上表写死真实节点名。但请注意：

1. **`Yuan_*` / `H3*` 这批节点所属的节点包尚未确认名称**（不是 DaSiWa-Nodes，也不是 ComfyUI 原生）。
   首次运行请先跑：
   ```bash
   python comfy/build_workflow.py verify --workflow workflows/h3_sla_fused_t2va.json
   ```
   缺失节点会列出来。
2. **`CLIPLoader.type = "minimax"`** 是关键细节，写错会报 unknown type。
3. 你本地工作流用 `ManualSigmas` 手写 sigma —— 若 `BasicScheduler` 出来的效果对不上，
   改用 `ManualSigmas` 并套用上面的 6 步 / 8 步 sigma 表。
4. **10GB 档位务必启用 `H3StreamedBlocks` + `H3EvictTextEncoder`**，否则必 OOM。

## 8. 待办

- [ ] 确认 `Yuan_MiniMaxH3Video` / `H3StreamedBlocks` / `MiniMaxH3HybridLoader` 所属节点包名并写进 `config/registry.yaml`
- [ ] 用 `--verify` 校验一次核心模板
- [ ] 把 6 步 / 8 步 sigma 表作为 `turbo` 变体的可选调度写进构建器
