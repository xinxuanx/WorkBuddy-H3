# 07 — 调研资料与出处

> 全部结论基于 **2026-10-05** 的实测抓取（源码优先于 README）。
> 标注「未找到」的项目不要硬编进工作流。

---

## 1. GitHub 仓库

| 仓库 | 关键事实 | 状态 |
|---|---|---|
| **MiniMax-AI/MiniMax-H3** | 33B dense 单流 Omni-Transformer；AdaLN + MM-RoPE(t,h,w)；联合预测 video+audio latent；H3-Encoder 基于 Qwen3-VL-32B 取第 50 层 hidden states；VisualVAE `f16t4d24`；输出 4–15s/24FPS/短边 768/32kHz 立体声；两个 checkpoint：`FL2VA` 与 `Ref2VA` | ✅ |
| **MiniMax-AI/MiniMax-H3 的 `.agents/skills/` 与 `.claude/skills/`** | ★ **官方提示词技能 `h3-prompt-writing`**，两份字节数完全相同的副本。`SKILL.md`(2177B) + `references/base-en.txt`(15773B，222 行) + `references/ref-en.txt`(23553B，341 行) + `agents/openai.yaml`(240B)。frontmatter 明写 "Portable to any agent that can read local files … does not restrict the skill to OpenAI agents"。**已原样 vendored 到 `spec/official/`** | ✅ |
| **QwenLM/Qwen-Image-2.1** | 2026-09-20 发布，统一文生图+图像编辑（同一权重、同一 `QwenImage21Pipeline`）；7B/32 层 Single-Stream DiT + Qwen3-VL 8B 编码器 + 64 通道 RGBA VAE；原生 2K；最多 10 张参考图 | ✅ |
| **krea-ai/krea-2** | 2026-06-22，12B DiT，单流 MMDiT + rectified flow；发布 RAW + Turbo 两个完整 checkpoint；HF gated access；**通用 image reference 列为未来工作，当前只支持风格参考**；训练上限 1024px，无原生 2K | ✅ |
| **Comfy-Org/ComfyUI** | v0.38.0（2026-09-29）；新前端默认；Job API `/api/jobs`；`--fast` 是实验性枚举（`fp16_accumulation`/`fp8_matrix_mult`/`cublas_ops`/`autotune`），帮助文本明写 "untested and potentially quality deteriorating" | ✅ |
| **Comfy-Org/comfy-cli** | `comfy setup/install/update/launch/node install/model download/run/jobs`；全命令 `--json`；`registry-list` 存在但源码标 `hidden=True`（故官方文档查不到）；`COMFY_LOCAL_URL` 指向外部实例 | ✅ |
| **Comfy-Org/ComfyUI-Manager** | cm-cli 语法；snapshot 在 `<USER_DIRECTORY>/__manager/snapshots`（≥0.3.76）；批量装节点需 `config.ini` 的 `allow_git_url_install`/`allow_pip_install`（默认 false，仅 loopback） | ✅ |
| **Comfy-Org** 其它 | `ComfyUI_frontend`、`comfy-kitchen`、`workflow_templates`、`Comfy-Desktop`、**`comfy-mcp`**（stdio、40 tools、需 comfy-cli>=1.14.0、AGPL-3.0-or-Commercial）、`comfy-python-sdk`、`comfy-api-proxy`、`comfy-quants`。**不存在** `comfyui-training` | ✅ |
| **openclaw/openclaw** | = Clawdbot → Moltbot → OpenClaw（301 跳转验证）；391k stars，MIT；Gateway 本地控制平面 + 20+ 渠道；OpenClaw Foundation 托管；Node 24.16+。**无 "bot mode" 术语** | ✅ |
| **NousResearch/hermes-agent** | 251k stars，MIT；自改进 Agent 运行时；Bot Mode = **多角色 profile 花名册 UI**，"no background daemons"；无人值守靠 `approvals.unattended_mode` + YOLO；有 API Server / A2A / Webhooks / peer | ✅ |
| **NikoDemon80/ComfyUI-H3-Motion-Context** | 需 ComfyUI ≥0.34；`H3 Motion Context`（context_length 推荐 22、audio 推荐 24）、Trim、Save/Load Latent、Chain、Seam Probe；不改源码，首次运行 `layout_contract.py` | ✅ |
| **veda-sparse/Veda-on-ComfyUI** | 注册表 id `veda-sparse-attention`；**需 ComfyUI ≥0.38.0**；唯一节点 `Veda Sparse Attention (MiniMax H3)`；predictor 275MB；Triton INT8（SM80+）/ MLX；**与原生 Model Sparse Attention 互斥** | ✅ |
| **sepiablue-ai/ComfyUI-H3-X2-Stream** | 三个节点：`H3 X2 Prepare INT8 VAE`、`H3 X2 Decode + Stream Save`、`H3 Chunk FeedForward (X2 Stream)`；**VAE/编码 IO 层，不是注意力**；实测 ComfyUI 0.37.0 / RTX 4070 12GB | ✅ |
| **darksidewalker/ComfyUI-DaSiWa-Nodes** | GPL v3，v0.4.78；`MiniMaxH3Director`（T2VA/I2VA/L2VA/FL2VA/REF2VA/Inpaint 一个节点全包，REF2VA = 9图+3视频+3音频，单段 2–15s，frame_rate 默认 24，Auto 分辨率 = 短边 768）、`DaSiWa_SeedControl`（64-bit）、`DaSiWa_NodeStatusSwitch`、`DaSiWa_LTX2LoraLoader`（10 槽）、`DaSiWa_MetadataImageSaver`、`DaSiWa_EnhancedVideoCombine`、`DaSiWaH3ContinuityPublish`（continuity 检查点在 `output/df_h3_continuity/`） | ✅ |

---

## 2. HuggingFace

| 仓库 | 关键事实 |
|---|---|
| **WarmBloodAban/Minimax-h3_Singularity** | 融合+深度微调的完整权重（非 LoRA），基于 ref/fl/b25-49 等 checkpoint，3 天剪枝消除高步数伪影。三档：int8 34GB / pruned int8 21GB / **pruned w4a8 11.8GB**。卖点：HDR、远景人脸修复、去油光、武打/奇幻 VFX、100% 保留 prompt adherence。**steps/cfg/sampler/显存未给出** |
| **MATLOWAI/minimax-h3-fused-turbo-int8-convrot** | 21GB。三层融合：pruned fl2va 底座 + **r1024 SVD 融入 (ref2va − fl2va) delta** + lightx2v Turbo 8-step@1.0 + Mystic v2.0@0.7。INT8 量化四个重 Linear，ComfyUI 原生 `comfy_quant` 布局 → 直接 UNETLoader。作者：**"run it at 4 steps"**。实测 16GB 峰值 11.0GiB/65s；RTX PRO 6000 96GB 4步 76s / 8步 103s / 25步 292s。附 5 个工作流（含 ROCm/lowvram 版） |
| **Comfy-Org/MiniMax-H3** | 官方重打包。`int8_convrot` 优先于 `fp8_scaled`（原话："prefer int8_convrot if you are able to use pytorch with cu130；fp8_scaled should only be used if you cannot use int8_convrot"）。VAE：fp16 5.21GB / int8_convrot 2.81GB / audio fp32 605MB。turbo LoRA 三个 |
| **Comfy-Org/Qwen-Image-2.1** | bf16 14.2GB / int8_convrot 7.26GB；text encoder qwen3vl_8b 三档；PE 提示词增强权重；`qwen_image_2.1_fun_controlnet_union` |
| **Kijai/MiniMax-H3-experimental** | **`minimax_h3_lynnreal_light_vae_int8_convrot` 2.14GB**（源权重 `stdstu123/LynnReal-Onmi-light-vae`），"about 1.3x faster for decoding"。w4a8 = 4-bit 权重 + int8-convrot 激活；w6a8 = 6-bit + int8-convrot。int8_convrot VAE 需 ComfyUI 0.36.0 才有约 2× 提速 |
| **multimodalart/h3-acceleration-arena** | 盲测 A/B 人工投票，约 26 个加速变体，200 条 prompt × t2v/i2v，124 帧/5.167s/16:9/768P，约 3700 片段。**榜单 gate 在 2500 票后公开，目前无排名**。已报告：lightx2v 两条 leg 响度差 12.4 dB（已归一化到 −23 LUFS）；FastVideo 探针 **已 withdrawn**（过锐化 + 一条 degenerate smeared blob） |
| **FastVideo/FastVideo-FastH3-Comfy** | 8-step v2 pruned int8_convrot 22.1GB；text encoder 27.1GB / nvfp4_awq 15.7GB |
| **smhfacct/Minimax-H3-fl2va-ref2va-hybrid-models** | hybrid 系列（本地 `minimax_h3_hybrid_fl2va_ref2va_b25-49-int8` 疑似来自此） |
| **Viggle/Qwen-Image-2.1-viggle-turbo** | DMD 蒸馏 5 步 rank-256 LoRA，固定 sigma `[1.0,0.875,0.75,0.5,0.25]`，`true_cfg=1.0`。**编辑仅 ≤3 张参考图，小字/长文本更易乱码，2K 未验证** |

---

## 3. Civitai

| 页面 | 关键事实 |
|---|---|
| **dasiwa-minimax-h3**（2877206） | 7 个版本：Hybrid v1/v2/v3、Hybrid Turbo v1/v2/**v3(3374439)**、Hybrid 8Turbo v1、Hybrid 4Turbo v1。Turbo v3 文件 int8 20.48GB + int4 12.25GB。作者推荐：非蒸馏 `res_multistep/simple` 或 `euler/simple`、Shift 10–12/3–5、20–25 步；Turbo `euler/simple` 或 `LCM/simple`、Shift 6–12/3–5、4 或 8 步。依赖：`MiniMaxH3Director` + `qwen3vl_32b_nvfp4_awq` + 视频 VAE + **音频 VAE fp32（REF2VA 必需）** + `taeh3.safetensors`；节点包：KJNodes、GGUF、DaSiWa-Nodes、MMH3-UltimateUpscale、ffmpeg |
| **dasiwa-krea2-or-turbo-or-raw**（2760803） | 4 个版本：DarkDesire V3 Turbo UC、CuteDisaster v2 Turbo UC、MirroredSkies v1 Turbo、MirroredSkies v1 Raw。Turbo = CFG 1、Euler/linear_quadratic 或 er_sde/simple、8 步、1536×1536；RAW = CFG 3.5、52+ 步。取向为 Unchained/NSFW/强风格化 |

---

## 4. fourthplace43 Labs

| 页面 | 结论 |
|---|---|
| **/labs/h3-vae-quality/en** | ComfyUI 0.35 + FP16 VAE vs 0.36 + 官方轻量 INT8 ConvRot VAE + `--fast fp16_accumulation`（RTX 5080 16GB，1152×640，Turbo 4 步，稀疏 10%）。纯解码 10.1s/243f：28.5s → 17.0s → **10.0s**；1408×800 编+解码 106.9s → 52.2s → **41.4s**。画质：平均差 1.2–1.3/255 灰阶，PSNR 42.1–43.0 dB，SSIM 0.983–0.988 —— **轻量权重无额外劣化**。整条生成 56.4s → 43.0s |
| **/labs/jev-sparse-comparison/en** | JEV 分配方式不改变生成时间（AI 分配 40.22s vs 均匀 37.56s 中位数）。**反向测试证伪**：翻转层描述文字 → 分配结果完全镜像（移动 6.49 分 vs 重复提问 0.11 分）。堆栈拆解：Turbo LoRA 4.68×、SLA 1.96–3.13×、叠加 9.19×（采样）/5.7×（wall time）。作者注明"逐层动态 keep 率调度是自建小节点，未改 ComfyUI 源码" |

---

## 5. 官方文档

| 文档 | 关键事实 |
|---|---|
| **docs.comfy.org/tutorials/video/minimax/minimax-h3** | H3 **原生支持**，无需插件。节点：`MiniMax H3 Image to Video`（t2va/fl2va）、`MiniMax H3 Reference to Video`（ref2va）、`MiniMaxH3SigmaShift`、`Model Sparse Attention`、`Model Attention Backend`。官方推荐：分辨率 **1344×768**（**不要设 1.0 MP**，会变 1376×768 超限）；`res_multistep` + `simple`；**shift 12 / audio_shift 3**；T2V/I2V 20 步（turbo 8 步）；R2V 20 步（漂移 25），reference turbo 4 步。**未给出 CFG 值**（走 BasicGuider）。警告：*"at 4 steps a reference can end up barely applied..."*。稀疏 `sink_conditioning = exact_kv_and_rows` |
| **docs.comfy.org/.../qwen-image-2-1** | 原生 Day-0 支持，无需插件。模板 `image_qwen_image_2_1_t2i` / `_image_edit` / `_background_removal`。节点含 `TextEncode Qwen Image 2.1`（最多 16 图槽）、`Qwen Image 2.1 Cache`、`TextGenerate`（PE）、`ResolutionSelector`。ComfyUI 模板 25 步 / cfg 1 / euler / simple |
| **docs.comfy.org/.../krea-2** | 原生支持。模板 `image_krea2_turbo_t2i`、`image_krea2_turbo_int8_image_style_reference`。Turbo 8 步 / CFG 0 / mu 1.15；RAW 52 步 / CFG 3.5 |
| **MiniMax-H3 `skills/h3-prompt-writing/references/ref-en.txt`** | REF2VA 六段固定顺序；`<Picture N>`/`<Subject N>`/`<Video N>`/`<Audio N>` 独立编号；**明确否定 "Picture 1 from Shot 1" 写法**；只用于定义主体的图应内联进 `<Subject N>`；`retention_analysis` 四种关系枚举 |

---

## 6. 许可证

| 模型 | 许可 | 商用 |
|---|---|---|
| Qwen-Image-2.1 | **Qwen Research License** | ⚠️ **仅非商用研究/评估，商用需另取得商业许可** |
| Qwen-Image / Qwen-Image-Edit-2509 | Apache 2.0 | ✅（合规替代路线） |
| Krea 2 | Krea 2 Community License | 年营收 < 100 万美元可免费商用；分发名称须以 "Krea" 开头 |
| comfy-mcp | AGPL-3.0-or-Commercial | 注意传染性 |

---

## 7. 明确「未找到」清单（不要硬编）

- ❌ MiniMax-H3 参考图的分辨率上限 / 宽高比 / 格式要求
- ❌ H3 提示词长度上限（只有 token 用量示例：T2VA 8565 / I2VA 22822 / REF2VA 39299）
- ❌ H3 负面提示词支持（官方与指南均未提及）
- ❌ H3 官方 CFG 值（走 BasicGuider，无此概念）
- ❌ H3 官方单卡显存门槛
- ❌ "FLF2VA" 命名（官方不存在，即 FL2VA 首尾帧用法）
- ❌ Singularity 的 steps / cfg / sampler / 分辨率 / 显存
- ❌ Qwen-Image-2.1 官方 CFG 默认值与 shift 数值（仅称 dynamic shifting）
- ❌ Krea 2 官方显存数字；Krea 2 的 GGUF / Nunchaku 量化生态
- ❌ Krea 2 官方中文文字渲染基准分数
- ❌ OpenClaw 的 "bot mode"（不存在）
- ❌ Hermes Agent 与 Hermes-4 模型的内置绑定关系
- ❌ `comfy-mcp` 40 个 tool 的完整清单
- ❌ Qwen-Image-Edit-2509 的多图参考上限

---

## 8. 版本下限冲突矩阵（部署前必查）

| 依赖 | 最低版本 |
|---|---|
| H3 任意关键帧锚点 | ComfyUI 0.34+ |
| int8_convrot VAE 提速 | ComfyUI 0.36.0 |
| **Veda** | **ComfyUI ≥ 0.38.0** |
| X2-Stream | 实测 0.37.0 |
| ComfyUI-Manager 完整功能 | ComfyUI ≥ 0.3.76 |
| comfy-mcp | comfy-cli >= 1.14.0 |

> ⚠️ **Veda 要 ≥0.38，X2-Stream 实测 0.37** —— 两者都要时以 0.38+ 为准并自行验证 X2-Stream。
