# 06 — 工作流矩阵：SLA / Veda × 融合 turbo / 外挂 turbo

---

## 1. ★ 注意力加速：ComfyUI 现在到底原生支持了吗？

**没有。** 只覆盖了两条，其它都还是插件。

| 方案 | 状态 | 入口 |
|---|---|---|
| **SLA / sol-attn / VSA** | ✅ **原生** | 节点 **`Model Sparse Attention`**（`node_id: BlockSparseAttention`，category `model/patch`，`is_experimental=true`） |
| **SageAttention 1/2/3** | ✅ **原生** | `--use-sage-attention` + `pip install sageattention`（版本靠 pip 包决定，无独立开关） |
| FlashAttention / xformers / split / quad | ✅ 原生 | `--use-flash-attention` 等 |
| Comfy Kitchen attention | ✅ 原生 | `--use-ck-attention`、`--enable-triton-backend` |
| torch.compile | ✅ 原生 | 节点 `TorchCompileModel` |
| EasyCache / LazyCache | ✅ 原生 | 节点 `EasyCache`、`LazyCache` |
| CFG-Zero\* / CFG-Norm / APG / PAG / NAG / SLG / ToMe / HyperTile | ✅ 原生 | 对应节点 |
| fp16 累加 / fp8 matmul / cublas / autotune | ✅ 原生（**实验性**） | `--fast [fp16_accumulation\|fp8_matrix_mult\|cublas_ops\|autotune]` |
| **Veda** | ❌ **需插件** | `comfy node install veda-sparse-attention`，**要求 ComfyUI ≥ 0.38.0** |
| **JEV** | ❌ 需插件 + 云端 API | ❌ **本项目已否决，见 §2** |
| **X2-Stream** | ❌ 需插件 | 但它是 **VAE/编码 IO 层，不是注意力** |
| **Radial Attention** | ❌ 需插件 | 核心 `comfy_extras/` 无此节点 |
| **TeaCache / MagCache** | ❌ 需插件 | 核心只有 EasyCache/LazyCache |

### 原生 SLA 节点的参数（ComfyUI 0.38）

```yaml
node: "Model Sparse Attention"     # node_id: BlockSparseAttention
method: sol-attn                   # 三选一：sol-attn | sla | vsa
  # sol-attn: tau = 1.3            ← base 权重用这个
  # sla:      keep_percent = 10.0
  # vsa:      keep_percent = 10.0（需 FastH3 权重）
start_percent: 0.2
end_percent: 1.0
dense_blocks: "0, 1, 47-49"
min_tokens: 12288
extra_tokens: 256
sink_conditioning: exact_kv_and_rows   # ★ H3 专用，保住 reference rows 与音频质量
verbose: false
```

内核来自 `comfy_kitchen`（`ck.sol_attn` 等），`HEAD_DIM=128`、`BLOCK_SIZE=64`，H3 走 4096-token 分块。
出处：SLA = "SLA: Beyond Sparsity in Diffusion Transformers via Fine-Tunable Sparse-Linear Attention"（arXiv 2509.24006）。
实测加速：**1.96× – 3.13×**。

---

## 2. ★ JEV —— 砍掉，统一叫 SLA

**JEV 不是注意力方案。** 它是 TypeSafe AI 的决策模型（`jev-1.13.0`），不生成内容，
通过 `TYPESAFE_API_KEY` 云端调用，为每层从 1%/3%/5%/10% 里挑一个 keep 率 —— **底层仍然是原生 SLA**。

### 实测数据（sepiablue-ai 的 `ComfyUI-MiniMax-H3-W4A4-VSA` 实验分支）

| 配置 | 耗时 |
|---|---|
| 基线 | 366.72 s |
| 固定 5% | **212.20 s** |
| Jev 自适应 | **219.15 s** ← **反而慢 6.95 s** |
| 固定 1% | 200.71 s（最快） |

`fourthplace43.com/labs/jev-sparse-comparison/en` 的结论一致：
- 分配方式不改变生成时间（AI 分配 40.22s vs 均匀 37.56s 中位数）
- **反向测试证伪**：只把给模型的"层描述文字"反过来问，分配结果**完全镜像翻转**
  （移动 6.49 分 vs 重复提问 0.11 分）→ 说明它并没真正"看懂"层
- 作者自己也注明"这是 SLA+Jev 整体效果，不是 Jev 相对固定 SLA 的优势，质量同等性未认定"

### 决策

> **JEV 从本项目中移除。所有涉及 JEV 的命名统一改为 `SLA`。**
> 若将来需要"逐层动态 keep 率调度"，那是**自建**的事（fourthplace43 明确写：
> "未改 ComfyUI 源码，只加了一个小节点，职责是逐步/逐层替换 ratio"），不叫 JEV。

---

## 3. ★ Veda 与 SLA：一个工作流还是两个？

### 它们互斥（硬约束）

Veda 插件 README **明确要求**：不要在 H3 上同时挂 ComfyUI 原生 `Model Sparse Attention`，
因为后者会**整体替换 attention block，使 Veda 永不生效**。

### 方案对比

| 方案 | 优点 | 缺点 |
|---|---|---|
| A. 做两条完全独立的工作流 JSON | 最直白、不会出错 | 维护成本 ×2，改一处要改两份 |
| B. 一条链上串联两个节点，运行时 bypass 切换 | 单文件 | 运行时切换依赖 UI/节点模式，API 提交不好控 |
| **C. ★ 一份槽位模板 → 构建器生成 N 份 JSON** | 单源维护、产物确定、最适合 API 驱动 | 需要构建脚本 |

### 选定：方案 C

**实现：**
- 模板 `comfy/templates/h3_core.json` 用槽位占位
- `comfy/build_workflow.py` 根据 `attention ∈ {sla, veda, none}` **决定发射哪个节点**
  （互斥，二选一，**绝不同时发射**）
- 产物落在 `workflows/`：

```
workflows/
├── h3_sla_fused.json
├── h3_sla_lora.json
├── h3_sla_none.json
├── h3_veda_fused.json
├── h3_veda_lora.json
├── h3_veda_none.json
├── h3_dense_fused.json
├── h3_dense_lora.json
└── h3_dense_none.json
```

> 手工调试时仍可在 ComfyUI UI 里把两个节点串起来、靠 bypass 切换（方案 B），
> 但**提交给 API 的一律是构建器产物**，保证确定性。

### 什么时候用 Veda，什么时候用 SLA

| 场景 | 选择 | 理由 |
|---|---|---|
| 默认 / 生产主力 | **SLA** | 零下载、原生、无版本门槛、官方教程推荐 |
| ComfyUI ≥ 0.38 且追求极致速度 | **Veda** | 注意力部分 7.1×、端到端 2.9×（RTX 5070 12GB 实测） |
| A/B 对照 | **none (dense)** | 建立质量基线 |
| 排查质量问题 | **none (dense)** | 先排除稀疏注意力是否是元凶 |

⚠️ **10GB 档位提醒**：Veda 的 predictor 是 275MB 额外文件，且需要 ComfyUI ≥0.38；
若你的 ComfyUI 卡在 0.37（X2-Stream 作者实测版本），先用 SLA。

---

## 4. ★ 融合 turbo vs 未融合 turbo

### 三种形态

| 形态 | 说明 | 步数 | 工作流差异 |
|---|---|---|---|
| **fused** | turbo 已融进权重（MATLOWAI、DaSiWa Turbo v3） | **4** | **不发射 LoRA 节点** |
| **lora** | 权重未融合，外挂官方 turbo LoRA | 4 或 8 | **发射 `LoraLoaderModelOnly`** |
| **none** | 非蒸馏，走全步数 | 20（漂移 25） | 不发射 LoRA，步数拉满 |

### 可用 turbo LoRA

```
models/loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors
models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
models/loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors
```

### ⚠️ 官方警告（必须写进构建器校验）

> *"at 4 steps a reference can end up barely applied, and a subject's pose or face angle can
> drift away from the reference"*

**规则：`mode=ref2va` 且 `require_identity_fidelity=true` 时，禁止 4 步。**
`build_workflow.py` 里做了硬校验，会直接报错而不是默默产出漂移的视频。

### 切换方式

改 `config/registry.yaml` 的 `h3_weights[*].turbo`，或直接传参：

```bash
python comfy/build_workflow.py --attention sla --turbo fused --mode ref2va \
       --weight dasiwa_hybrid_turbo_v3_int4 --tier t10 --out workflows/
```

---

## 5. 完整矩阵（3 × 3 = 9 变体）

| 变体 | 注意力 | turbo | 步数 | 适用 |
|---|---|---|---|---|
| `h3_sla_fused` | SLA（原生） | 已融合 | 4 | ★ **默认主力** |
| `h3_sla_lora` | SLA | 外挂 LoRA | 4–8 | 非融合权重（如 Singularity） |
| `h3_sla_none` | SLA | 无 | 20 | 质量优先 hero shot |
| `h3_veda_fused` | Veda（插件） | 已融合 | 4 | ComfyUI ≥0.38，极致速度 |
| `h3_veda_lora` | Veda | 外挂 LoRA | 4–8 | 同上 + 非融合权重 |
| `h3_veda_none` | Veda | 无 | 20 | hero shot + 极致速度 |
| `h3_none_fused` | 无（dense） | 已融合 | 4 | A/B 对照 |
| `h3_none_lora` | 无（dense） | 外挂 LoRA | 4–8 | A/B 对照 |
| `h3_none_none` | 无（dense） | 无 | 20 | 质量基线 |

> 命名说明：构建器的 `--attention` 取值是 `sla / veda / none`，
> 所以文件名是 `h3_none_*`。**`none` ≡ `dense`（全注意力，不稀疏）**，两者指同一件事。

### 模式维度为什么不占矩阵

`MiniMaxH3Director` 一个节点的 `mode` 输入就能切
`t2va / i2va / l2va / fl2va / ref2va` —— **模式是运行时的一个字符串，不是一套工作流**。
所以模式维度被折叠掉了，不产生 9 × 6 = 54 份文件。

---

## 6. 正交叠加项（不与矩阵相乘，按需挂载）

| 模块 | 层 | 可否与 SLA 叠加 | 说明 |
|---|---|---|---|
| **X2-Stream** | VAE / 编码 IO | ✅ 可以 | 解码与 NVENC 异步重叠流式落盘；124f@24fps 544×960→1088×1920 带音频约 59.7s。**10GB 档位强烈建议** |
| **H3-Motion-Context** | 分段续接 | ✅ 可以 | 跨 clip 连贯；需 ComfyUI ≥0.34 |
| **SageAttention** | 注意力后端 | ⚠️ 需验证 | 与 SLA/Veda 不同层，但要先 A/B |
| **H3 Chunk FeedForward** | 显存 | ✅ 可以 | `chunks=4` 降峰值显存（KJNodes） |
| **torch.compile** | 编译 | ⚠️ 需验证 | 节点 `TorchCompileModel` |

### H3-Motion-Context 要点（`ComfyUI-H3-Motion-Context`）

- 要求 **ComfyUI ≥ 0.34.0**；不改源码；首次运行 `layout_contract.py` 布局检查，失败即拒绝运行
- **`H3 Motion Context`**：`context_length` 推荐 **22**；`audio_context_length` 推荐 **24**（3 的倍数对齐 40Hz 音频网格）
- 放在 `MiniMaxH3ImageToVideo` / `MiniMaxH3ReferenceToVideo` 之后、guider/sampler 之前
- `first_frame` 锚点会被丢弃并警告，`last_frame` 保留
- **`H3 Motion Context Chain`**：Load/Save/Chain **必须在同一个 canvas group**，否则按钮失效
- ComfyUI 原生 Save/Load Latent **不能**处理 H3 双流 latent，必须用它的专用节点
- 限制：latent 路径中途不能改分辨率；推荐关闭 Spectrum；提示词需 "airlock" 过渡

---

## 7. 10GB 档位的推荐组合

```
主链路：h3_sla_fused
  权重：dasiwa_hybrid_turbo_v3_int4（12.25GB）或 Singularity pruned w4a8（11.8GB）
  步数：4（非强身份场景）
  分辨率：544×960
  VAE：lynnreal_light_int8_convrot（2.14GB）
  叠加：X2-Stream（流式落盘）+ H3 Chunk FeedForward chunks=4
  SLA：sink_conditioning = exact_kv_and_rows

Hero shot：h3_sla_none（20 步）或 h3_sla_lora（8 步）
  权重：Singularity pruned w4a8
  ⚠️ mode=ref2va 且要求强身份一致 → 禁止 4 步
```
