# 01 — 硬件分层与环境准备

## 0. 你的机器（实测）

| 项 | 值 |
|---|---|
| GPU | NVIDIA GeForce RTX 3080 **10 GB** |
| 驱动 | 610.88 |
| 档位 | **t10**（本项目最低档） |

**这决定了后面所有决策。** 请把这句话刻在脑子里：

> H3 是 33B 单流 Transformer，最小可用量化权重也要 11.8GB，**装不进 10GB 显存**。
> 所以 10GB 档位**必然走 CPU offload**，而 offload 的成本 = 步数 × 权重体积。

## 1. offload 成本模型（为什么 10GB 必须 4 步 + int4/w4a8）

每采样一步，都要把完整权重从系统内存搬到显存一次。

```
单步搬运量 ≈ 权重文件字节数
总搬运量   = 步数 × 权重字节数
PCIe 4.0 x16 实测带宽 ≈ 12–15 GB/s（分页内存更低）
```

| 组合 | 总搬运量 | 纯搬运耗时（不含计算） |
|---|---|---|
| 20 步 × int8 21GB | 420 GB | ~30–35 s（乐观值，实际更长） |
| 8 步 × int8 21GB | 168 GB | ~12–14 s |
| **4 步 × w4a8 11.8GB** | **47 GB** | **~4 s** ✅ |
| 20 步 × w4a8 11.8GB | 236 GB | ~17–20 s |

**结论：10GB 档位的铁律是 `4 步 + w4a8/int4 + 低分辨率`。**
任何"我试试 20 步"的想法，在 10GB 上都是几十分钟一个 5 秒片段。

## 2. 显存估算（10GB 档位，REF2VA）

| 组件 | 体积 | 策略 |
|---|---|---|
| DiT 权重 | 11.8–12.25 GB | 常驻不了 → `--lowvram` 逐层 offload |
| text encoder (Qwen3-VL-32B) | nvfp4_awq 15.7 GB | 同样要 offload；**只在编码阶段用，用完即释放** |
| 视频 VAE | 2.14 GB (lynnreal light int8) | 解码阶段才加载 |
| 音频 VAE | 0.605 GB fp32 | REF2VA 必需 |
| latent 激活（544×960×124f） | ~1–2 GB | 取决于帧数与是否 chunked |

**关键优化：文本编码器 ≠ 每帧都要。** 一个 job 内 prompt 与参考图固定，编码只做一次。因此
`--lowvram` 下 text encoder offload 的代价是一次性的，不必过度担心。

## 3. ComfyUI 版本下限矩阵（会互相冲突，务必核对）

| 依赖 | 最低 ComfyUI 版本 | 说明 |
|---|---|---|
| H3 原生支持 | 0.34+（任意关键帧锚点） | `MiniMaxH3ImageToVideo` / `MiniMaxH3ReferenceToVideo` |
| int8_convrot VAE 提速 | **0.36.0** | 不到 0.36 拿不到约 2× 解码提速 |
| **Veda 插件** | **≥ 0.38.0** | 硬性要求 |
| X2-Stream | 实测 0.37.0 | 依赖 H3 `decode(output_buffer=)` |
| ComfyUI-Manager 完整功能 | ≥ 0.3.76 | 快照目录路径在此版本变更 |
| comfy-mcp（可选） | comfy-cli >= 1.14.0 | AGPL-3.0-or-Commercial |

> ⚠️ **冲突点**：Veda 要 ≥0.38，X2-Stream 作者实测 0.37。若两者都要，以 0.38+ 为准并自行验证 X2-Stream。

**推荐基线：ComfyUI 0.38.x 稳定版**（当前 v0.38.0 发布于 2026-09-29）。

## 4. 环境搭建（一次性）

```bash
# 1) 解压便携版到 F:\ComfyUI（你已有 F:\ComfyUI-portable-nvidia.7z）
#    目标：F:\ComfyUI\

# 2) 安装 comfy-cli（Python 3.10+）
pip install comfy-cli
comfy setup -y

# 3) 安装/更新 ComfyUI 到 0.38
comfy install --fast-deps

# 4) 装自定义节点（registry id 必须小写）
comfy node install comfyui-kjnodes
comfy node install comfyui-gguf
comfy node install dasiwa-nodes            # MiniMaxH3Director 所在包
comfy node install veda-sparse-attention   # 仅当走 Veda 链路
# X2-Stream 与 H3-Motion-Context 走 git 安装：
#   git clone https://github.com/sepiablue-ai/ComfyUI-H3-X2-Stream custom_nodes/ComfyUI-H3-X2-Stream
#   git clone https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context custom_nodes/ComfyUI-H3-Motion-Context
#   git clone https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes custom_nodes/ComfyUI-DaSiWa-Nodes

# 5) 装 SageAttention（可选，Veda/SLA 之外的兜底）
pip install sageattention

# 6) 装本项目适配层依赖
pip install websocket-client pyyaml
```

> **无头装节点的坑**：ComfyUI-Manager 的 `POST /customnode/install/git_url` 受 `config.ini`
> 的 `allow_git_url_install` / `allow_pip_install` 控制，**默认 false**，且只在 loopback 监听时生效。
> 自动化部署前必须先改 `config.ini` 再重启 ComfyUI，否则静默失败。

## 5. 启动参数（t10 档位）

```bash
comfy launch -- --listen 127.0.0.1 --port 8188 \
  --lowvram \
  --reserve-vram 0.6 \
  --async-offload 2 \
  --fast fp16_accumulation \
  --disable-auto-launch
```

参数说明（均来自 ComfyUI `cli_args.py` 实测）：

| 参数 | 作用 | 注意 |
|---|---|---|
| `--lowvram` | 激进 offload 到内存 | 会**变慢**，但 10GB 没得选 |
| `--reserve-vram 0.6` | 预留 0.6GB 给系统，防 OOM | |
| `--async-offload 2` | 异步卸载流，减少等待 | |
| `--fast fp16_accumulation` | fp16 累加，实验性 | 帮助文本明写 "untested and potentially quality deteriorating"，需 A/B 验证 |
| `--disable-smart-memory` | **不建议常开** | 会让模型激进卸载，变慢；只在 OOM 频繁时开 |
| `--use-sage-attention` | 启用 SageAttention | 与 SLA/Veda **不同层**，可叠加但要先验证 |

## 6. 显存档位切换

改 `config/registry.yaml` 里的 `hardware_tiers` 即可，代码会自动取用对应分辨率/步数/权重/VAE。
新增一台机器 = 加一个 tier，不改任何代码。

## 7. 10GB 档位的现实预期

参考数据（RTX 5070 12GB，1344×768 / 124f / 8 步 Turbo）：

| 配置 | 耗时 |
|---|---|
| 默认注意力 | 40.7 s/步 |
| + SageAttention | 24.8 s/步 |
| + Veda | 14.0 s/步 |

10GB 卡还要叠加 offload 开销。粗估 **t10 档位单个 5 秒片段 2–5 分钟**。
据此规划产能：24 小时不间断 ≈ 300–700 片段/天（理论上限，实际按 50% 计入）。

> 如果要做真正的"批量生产"，**建议升级到 24GB+**（3090/4090/A5000）。
> 架构已按档位参数化，换卡只改配置。
