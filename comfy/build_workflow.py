r"""
工作流构建器 —— 槽位模板 → ComfyUI API JSON

为什么存在：
  Veda 与 SLA 互斥、turbo 有 fused/lora/none 三态、硬件档位决定分辨率与步数。
  若手工维护 3 × 3 × 5(mode) = 45 份 JSON 必然出错。
  所以只维护「一份带条件的槽位模板」，运行期组合出确定产物。

节点名来源：从真实可跑的工作流
  F:\H3\MiniMax-H3一键短剧V7.5_Singularity_PDMD_LynnReal_SOP.json 提取，
  不是猜的。若你的 ComfyUI 缺节点，用 `--verify` 先查。

用法：
  python comfy/build_workflow.py build  --tier t10 --weight singularity_pruned_w4a8 \
         --attention sla --turbo lora --mode ref2va --out workflows/
  python comfy/build_workflow.py derive --from "F:/H3/某工作流.json" --out comfy/templates/
  python comfy/build_workflow.py verify --workflow workflows/h3_sla_lora_ref2va.json
  python comfy/build_workflow.py matrix --out workflows/
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "config" / "registry.yaml"
TEMPLATES = ROOT / "comfy" / "templates"

try:
    import yaml
except ImportError:
    yaml = None


# =========================================================================== #
# 配置加载
# =========================================================================== #
def load_registry() -> dict:
    if yaml is None:
        raise SystemExit("需要 pyyaml：pip install pyyaml")
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


class ValidationError(Exception):
    pass


# =========================================================================== #
# 硬校验 —— 构建期拦截，不产出坏结果
# =========================================================================== #
def validate(reg: dict, *, family: str, tier: str, weight: str, attention: str, turbo: str,
             mode: str, steps: int, ref_images: list[str], ref_seconds: float | None,
             require_identity_fidelity: bool, comfy_version: str | None) -> list[str]:
    """返回警告列表；致命问题直接抛 ValidationError。"""
    warns: list[str] = []

    if family == "qwen21":
        # Qwen-Image-2.1 校验：只检查档位是否存在
        tiers = reg["hardware_tiers"]
        if tier not in tiers:
            raise ValidationError(f"未知档位 {tier}，可选：{list(tiers)}")
        return warns

    tiers = reg["hardware_tiers"]
    weights = reg["h3_weights"]
    limits = reg["h3_reference_limits"]

    if tier not in tiers:
        raise ValidationError(f"未知档位 {tier}，可选：{list(tiers)}")
    if weight not in weights:
        raise ValidationError(f"未知权重 {weight}，可选：{list(weights)}")

    w = weights[weight]
    t = tiers[tier]

    # 1) 权重是否支持该模式
    modes = w.get("modes", [])
    if modes and mode not in modes:
        raise ValidationError(
            f"权重 {weight} 不支持模式 {mode}；它支持：{modes}")

    # 2) 档位 vs 权重体积
    size = w.get("size_bytes") or 0
    cap = t.get("max_weight_bytes") or 0
    if size and cap and size > cap:
        warns.append(
            f"[档位] {weight} ({size/1e9:.2f}GB) 超过 {tier} 建议上限 "
            f"({cap/1e9:.0f}GB)，将走 CPU offload，速度显著下降")

    # 3) 注意力方案互斥
    if attention not in ("sla", "veda", "none"):
        raise ValidationError(f"未知注意力方案 {attention}")
    if attention == "veda" and comfy_version and _v(comfy_version) < _v("0.38.0"):
        raise ValidationError("Veda 需要 ComfyUI >= 0.38.0")
    if attention == "veda":
        warns.append("[互斥] Veda 与原生 Model Sparse Attention 不能共存；"
                     "本构建器只会发射 Veda 节点")

    # 4) ★ 官方已知漂移问题：ref2va + 4 步 + 强身份一致
    if mode == "ref2va" and steps <= 4 and require_identity_fidelity:
        raise ValidationError(
            "官方警告：4 步 turbo 下 reference 可能几乎不生效，人物姿势/脸角度会漂移。\n"
            "  → mode=ref2va 且 require_identity_fidelity=true 时禁止 4 步。\n"
            "  → 请把 steps 提到 8 或以上，或显式设置 --allow-4step-ref")

    # 5) turbo 三态与权重声明一致性
    declared = w.get("turbo")
    if turbo == "fused" and declared != "fused":
        warns.append(f"[turbo] {weight} 的 turbo 声明为 {declared!r}，"
                     f"但你请求 fused；若权重未融合 turbo，结果会退化")
    if turbo == "lora" and declared == "fused":
        warns.append(f"[turbo] {weight} 已融合 turbo，又外挂 LoRA 会导致过冲")

    # 6) 参考资产限额
    lim = limits.get("ref2va", {})
    if mode == "ref2va":
        if len(ref_images) > lim.get("images", 9):
            raise ValidationError(f"REF2VA 参考图 > {lim.get('images')} 张")
    elif mode in ("i2va", "fl2va"):
        if len(ref_images) > 2:
            raise ValidationError(f"{mode} 最多 2 张参考图")
    if ref_seconds is not None and not (2 <= ref_seconds <= 15):
        raise ValidationError(f"参考片段时长 {ref_seconds}s 越界（须 2–15s）")

    return warns


def _v(s: str) -> tuple:
    try:
        return tuple(int(x) for x in re.findall(r"\d+", s)[:3])
    except Exception:
        return (0,)


# =========================================================================== #
# 条件节点发射
# =========================================================================== #
def build(reg: dict, *, tier: str, weight: str, attention: str, turbo: str,
          mode: str, seed: int = 0, steps: int | None = None,
          res: str | None = None, prompt: str = "", ref_images: list[str] | None = None,
          require_identity_fidelity: bool = False, allow_4step_ref: bool = False,
          comfy_version: str | None = None, family: str = "core",
          first_frame: str = "", last_frame: str = "",
          negative_prompt: str = "", resolution: int | None = None,
          spectrum: bool = True, cache: bool = True) -> dict:
    ref_images = ref_images or []

    # ------------------------------------------------------------------ #
    # Qwen-Image-2.1 setting image branch
    # ------------------------------------------------------------------ #
    if family == "qwen21":
        warns = validate(reg, family=family, tier=tier, weight=weight, attention=attention,
                         turbo=turbo, mode=mode, steps=steps or 25, ref_images=ref_images,
                         ref_seconds=None, require_identity_fidelity=False,
                         comfy_version=comfy_version)
        for m in warns:
            print(f"  ⚠ {m}", file=sys.stderr)

        qwen = reg.get("setting_image_models", {}).get("qwen_image_2_1", {})
        tmpl = json.loads((TEMPLATES / "qwen21_setting_image.json").read_text(encoding="utf-8"))

        slots = {
            "{{UNET_NAME}}":      qwen.get("files", {}).get("diffusion_models", "qwen_image_2.1_int8_convrot.safetensors"),
            "{{CLIP_NAME}}":      qwen.get("files", {}).get("text_encoders", "qwen3vl_8b_int8_convrot.safetensors"),
            "{{VAE_NAME}}":       qwen.get("files", {}).get("vae", "qwen_image_2.1_vae_bf16.safetensors"),
            "{{PROMPT}}":         prompt,
            "{{NEGATIVE_PROMPT}}": negative_prompt,
            "{{RESOLUTION}}":     resolution or qwen.get("native_resolution_hint", 1280),
            "{{STEPS}}":          steps or qwen.get("steps", 25),
            "{{CFG}}":            qwen.get("cfg", 1),
            "{{SAMPLER}}":        qwen.get("sampler", "euler"),
            "{{SCHEDULER}}":      qwen.get("scheduler", "simple"),
            "{{SEED}}":           seed,
            "{{JOB_ID}}":         "qwen21job",
        }
        graph = _render(tmpl, slots)
        graph = _apply_conditions(graph, spectrum=spectrum, cache=cache)
        graph["_meta"] = {
            "family": family, "variant": "qwen21_setting", "tier": tier,
            "steps": steps or 25, "resolution": resolution or 1280,
            "seed": seed, "spectrum": spectrum, "cache": cache,
            "generator": "build_workflow.py",
        }
        return graph

    # ------------------------------------------------------------------ #
    # H3 core / x2 branch
    # ------------------------------------------------------------------ #
    t = reg["hardware_tiers"][tier]
    w = reg["h3_weights"][weight]

    if steps is None:
        base = w.get("recommended_steps", t.get("steps", 4))
        steps = base if isinstance(base, int) else base[0]
    if res is None:
        res = t["resolution_presets"]["portrait"]     # 默认竖屏（短视频）

    warns = validate(reg, family=family, tier=tier, weight=weight, attention=attention, turbo=turbo,
                     mode=mode, steps=steps, ref_images=ref_images, ref_seconds=None,
                     require_identity_fidelity=require_identity_fidelity
                     and not allow_4step_ref, comfy_version=comfy_version)
    for m in warns:
        print(f"  ⚠ {m}", file=sys.stderr)

    width, height = (int(x) for x in res.lower().split("x"))
    length = _frames_for(tier)

    tmpl_name = "h3_x2.json" if family == "x2" else "h3_core.json"
    tmpl = json.loads((TEMPLATES / tmpl_name).read_text(encoding="utf-8"))

    # --- 槽位取值表（唯一真源） ---
    slots = {
        "{{UNET_NAME}}":   w.get("file") or w.get("file_fl2va"),
        "{{WEIGHT_DTYPE}}": "default",
        "{{CLIP_NAME}}":   _pick_text_encoder(reg, tier),
        "{{CLIP_TYPE}}":   "minimax",              # 实测：CLIPLoader.type = "minimax"
        "{{VIDEO_VAE}}":   _pick_vae(reg, tier, "video"),
        "{{AUDIO_VAE}}":   _pick_vae(reg, tier, "audio"),
        "{{MODE}}":        MODE_LABEL.get(mode, mode),
        "{{PROMPT}}":      prompt,
        "{{WIDTH}}":       width,
        "{{HEIGHT}}":      height,
        "{{LENGTH}}":      length,
        "{{STEPS}}":       steps,
        "{{SHIFT_VIDEO}}": w.get("shift_video", 12) if isinstance(
                            w.get("shift_video", 12), int) else w["shift_video"][0],
        "{{SHIFT_AUDIO}}": w.get("shift_audio", 3) if isinstance(
                            w.get("shift_audio", 3), int) else w["shift_audio"][0],
        "{{SAMPLER}}":     _pick_sampler(w),
        "{{SCHEDULER}}":   "simple",
        "{{SEED}}":        seed,
        "{{TURBO_LORA}}":  _pick_turbo_lora(reg, turbo, mode),
        "{{TURBO_STRENGTH}}": 1.0,
        "{{JOB_ID}}":      "h3job",
        "{{SINK_CONDITIONING}}": "exact_kv_and_rows",
        "{{SPARSITY}}":    90.0 if family == "core" else 5.0,
        # ---- x2 家族专用槽位 ----
        "{{X2_DETAIL_VAE}}": reg["support_models"]["vae"]["x2_detail_v1"]["file"],
        "{{FIRST_FRAME}}":   first_frame or "SELECT_FIRST_FRAME.png",
        "{{LAST_FRAME}}":    last_frame or "SELECT_LAST_FRAME.png",
        "{{CHUNK_FFN}}":     4 if tier in ("t10", "t16") else 1,
    }

    graph = _render(tmpl, slots)
    graph = _apply_conditions(graph, attention=attention, turbo=turbo, mode=mode)

    # h3_x2.json uses the same unified Yuan_MiniMaxH3Video(30) node as h3_core.json,
    # so no FL2VA/REF2VA node switching is needed. X2-Stream handles dual-VAE decode
    # via H3X2PrepareINT8VAE(24) -> H3X2StreamSave(55).
    graph["_meta"] = {
        "family": family, "variant": f"h3_{attention}_{turbo}", "mode": mode, "tier": tier,
        "weight": weight, "steps": steps, "res": f"{width}x{height}",
        "length_frames": length, "seed": seed,
        "generator": "build_workflow.py",
    }
    if family == "x2":
        graph["_meta"]["upscale"] = {
            "in": f"{width}x{height}",
            "x2_out": f"{width*2}x{height*2}",
            "target_1080p": "需后处理 crop/resize 到 1920x1080（X2 是 2x，544*2=1088）",
        }
    return graph


MODE_LABEL = {
    # ComfyUI 侧 mode 下拉显示的是中文（实测自 Yuan_MiniMaxH3Video）
    "t2va": "纯文生视频", "i2va": "首帧图生视频", "l2va": "尾帧图生视频",
    "fl2va": "首尾帧生视频", "ref2va": "参考图生视频",
}


def _frames_for(tier: str) -> int:
    return {"t10": 124, "t16": 124, "t24": 243, "t48": 243}.get(tier, 124)


def _pick_text_encoder(reg: dict, tier: str) -> str:
    return reg["support_models"]["text_encoders"]["qwen3vl_32b_nvfp4_awq"]["file"]


def _pick_vae(reg: dict, tier: str, kind: str) -> str:
    if kind == "audio":
        return reg["support_models"]["vae"]["audio_fp32"]["file"]
    table = reg["support_models"]["vae"]
    key = reg["hardware_tiers"][tier].get("vae", "lynnreal_light_int8_convrot")
    if key not in table:                      # 配置键名写错时给可读的错误
        raise ValidationError(
            f"档位 {tier} 引用的 VAE '{key}' 不在 support_models.vae 里；"
            f"可选：{list(table)}")
    return table[key]["file"]


def _pick_sampler(w: dict) -> str:
    s = w.get("sampler", "res_multistep")
    return s if isinstance(s, str) else s[0]


def _pick_turbo_lora(reg: dict, turbo: str, mode: str) -> str:
    loras = reg["support_models"]["turbo_loras"]
    if mode == "ref2va":
        return loras["ref2v_turbo_4step"]
    return loras["fl2v_turbo_8step"] if turbo == "lora" else loras["fl2v_turbo_4step"]


# --------------------------------------------------------------------------- #
def _render(obj, slots: dict):
    """递归替换 {{SLOT}} 占位符。"""
    if isinstance(obj, dict):
        return {k: _render(v, slots) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_render(v, slots) for v in obj]
    if isinstance(obj, str):
        if obj in slots:                       # 整串就是槽位 → 保留原类型
            return slots[obj]
        out = obj
        for k, v in slots.items():
            if k in out:
                out = out.replace(k, str(v))
        return out
    return obj


def _apply_conditions(graph: dict, *, attention: str = "", turbo: str = "", mode: str = "",
                        spectrum: bool = False, cache: bool = False) -> dict:
    """按条件发射/剔除节点。

    模板里每个可条件节点带 `_cond`：
        "_cond": {"include_if": "attention == 'sla'"}
    被剔除的节点会从图中删除，并把它的输入链路短路到下游。
    """
    active = {"attention": attention, "turbo": turbo, "mode": mode,
              "spectrum": spectrum, "cache": cache}
    nodes = {k: v for k, v in graph.items() if not k.startswith("_")}
    graph = {k: v for k, v in graph.items() if k.startswith("_")}

    keep: dict[str, dict] = {}
    dropped: dict[str, dict] = {}
    for nid, node in nodes.items():
        cond = node.get("_cond")
        if cond:
            expr = cond.get("include_if", "True")
            try:
                ok = eval(expr, {"__builtins__": {}}, dict(active))  # noqa: S307
            except Exception as e:
                raise ValidationError(f"节点 {nid} 条件表达式错误: {expr} ({e})")
            if not ok:
                dropped[nid] = node
                continue
        node = {k: v for k, v in node.items() if k != "_cond"}
        keep[nid] = node

    # 短路：把被删节点的输入，接到消费它输出的下游节点上
    # 支持级联条件（A->B->C 多层删除），迭代直到所有 dropped 节点解析完毕
    for _ in range(len(dropped) + 1):
        progressed = False
        for dnid in list(dropped.keys()):
            dnode = dropped[dnid]
            src_link = _first_input_link(dnode)
            # 若输入链路指向另一个仍在 dropped 中的节点，先跳过等下一轮
            if src_link and src_link[0] in dropped:
                continue
            # 修改 keep 与其它 dropped 节点中引用 dnid 的输入
            all_nodes = list(keep.items()) + [(k, v) for k, v in dropped.items() if k != dnid]
            for nid, node in all_nodes:
                for k, inp in list(node.get("inputs", {}).items()):
                    if isinstance(inp, list) and len(inp) == 2 and str(inp[0]) == dnid:
                        if src_link is not None:
                            node["inputs"][k] = [src_link[0], src_link[1]]
                        else:
                            node["inputs"][k] = []
                        progressed = True
            del dropped[dnid]
        if not progressed:
            break
    graph.update(keep)
    return graph


def _first_input_link(node: dict):
    for inp in node.get("inputs", {}).values():
        if isinstance(inp, list) and len(inp) == 2:
            return inp
    return None


# =========================================================================== #
# derive —— 从已有可用工作流反向生成槽位模板（推荐做法）
# =========================================================================== #
def derive(src: Path, out_dir: Path) -> Path:
    """把你手上一个能跑通的 workflow（UI 格式或 API 格式）转成槽位模板。

    UI 格式会尽量转成 API 格式；识别不到的链路保持原样并打印提示。
    """
    data = json.loads(src.read_text(encoding="utf-8"))
    if "nodes" in data:                       # UI 格式
        graph = _ui_to_api(data)
    else:
        graph = data

    # 标记可条件节点：按类型识别
    COND_BY_TYPE = {
        "Model Sparse Attention": "attention == 'sla'",
        "Veda Sparse Attention (MiniMax H3)": "attention == 'veda'",
        "LoraLoaderModelOnly": "turbo == 'lora'",
    }
    for nid, node in graph.items():
        if not isinstance(node, dict):
            continue
        t = node.get("class_type")
        if t in COND_BY_TYPE:
            node["_cond"] = {"include_if": COND_BY_TYPE[t]}

    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{src.stem}.template.json"
    dst.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成模板：{dst}")
    print("提示：把需要参数化的值改成 {{SLOT}} 占位符，再用 build 渲染。")
    return dst


def _ui_to_api(ui: dict) -> dict:
    """UI 格式 → API 格式（尽力而为；widget 值按声明顺序回填）。"""
    nodes = {str(n["id"]): n for n in ui.get("nodes", [])}
    links = {}
    for lk in ui.get("links", []):
        if len(lk) >= 6:
            links[lk[0]] = (str(lk[3]), lk[4])     # link_id -> (src_node, src_slot)

    api: dict[str, dict] = {}
    for nid, n in nodes.items():
        if n.get("mode") in (2, 4):                # mute / bypass
            continue
        inputs: dict[str, list] = {}
        for inp in n.get("inputs") or []:
            if inp.get("link") is not None and inp["link"] in links:
                inputs[inp["name"]] = list(links[inp["link"]])
        wv = n.get("widgets_values") or []
        for i, w in enumerate(n.get("__widget_order__", [])):
            if i < len(wv):
                inputs[str(w)] = wv[i]
        api[nid] = {"class_type": n["type"], "inputs": inputs}
    return api


# =========================================================================== #
# verify —— 用 /object_info 校验节点是否真的存在
# =========================================================================== #
def verify(workflow: Path, host: str = "127.0.0.1:8188") -> int:
    import urllib.request

    graph = json.loads(workflow.read_text(encoding="utf-8"))
    try:
        with urllib.request.urlopen(f"http://{host}/object_info", timeout=20) as r:
            info = json.loads(r.read())
    except Exception as e:
        print(f"连不上 ComfyUI({host})：{e}")
        return 2

    missing = []
    for nid, node in graph.items():
        if nid.startswith("_") or not isinstance(node, dict):
            continue
        ct = node.get("class_type")
        if ct and ct not in info:
            missing.append((nid, ct))

    if not missing:
        print(f"✓ 全部节点在 ComfyUI({host}) 上存在")
        return 0
    print("✗ 缺失节点：")
    for nid, ct in missing:
        print(f"  [{nid}] {ct}")
    print("\n→ 用 comfy node install 或 git clone 补齐后重启 ComfyUI")
    return 1


# =========================================================================== #
def main() -> None:
    ap = argparse.ArgumentParser(description="H3 工作流构建器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--tier", default="t10")
    b.add_argument("--weight", required=True)
    b.add_argument("--attention", default="sla", choices=["sla", "veda", "none"])
    b.add_argument("--turbo", default="fused", choices=["fused", "lora", "none"])
    b.add_argument("--mode", default="ref2va",
                   choices=["t2va", "i2va", "l2va", "fl2va", "ref2va"])
    b.add_argument("--steps", type=int)
    b.add_argument("--res")
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--prompt", default="")
    b.add_argument("--out", default=str(ROOT / "workflows"))
    b.add_argument("--require-identity", action="store_true",
                   help="强身份一致（会禁用 ref2va 的 4 步）")
    b.add_argument("--allow-4step-ref", action="store_true")
    b.add_argument("--comfy-version")
    b.add_argument("--family", default="core", choices=["core", "x2", "qwen21"],
                   help="core=原生链路；x2=X2-Detail 2x 放大 + 异步 NVENC 落盘；qwen21=Qwen-Image-2.1 设定图")
    b.add_argument("--first-frame", default="")
    b.add_argument("--last-frame", default="")
    b.add_argument("--negative-prompt", default="", help="Qwen21 专用：负面提示词")
    b.add_argument("--resolution", type=int, help="Qwen21 专用：TextEncodeQwenImage21 resolution 参数")
    b.add_argument("--spectrum", action="store_true", default=True, help="Qwen21 专用：启用 Spectrum 加速")
    b.add_argument("--no-spectrum", action="store_false", dest="spectrum", help="Qwen21 专用：禁用 Spectrum")
    b.add_argument("--cache", action="store_true", default=True, help="Qwen21 专用：启用 KV Cache")
    b.add_argument("--no-cache", action="store_false", dest="cache", help="Qwen21 专用：禁用 KV Cache")

    d = sub.add_parser("derive")
    d.add_argument("--from", dest="src", required=True)
    d.add_argument("--out", default=str(TEMPLATES))

    v = sub.add_parser("verify")
    v.add_argument("--workflow", required=True)
    v.add_argument("--host", default="127.0.0.1:8188")

    m = sub.add_parser("matrix")
    m.add_argument("--tier", default="t10")
    m.add_argument("--weight", required=True)
    m.add_argument("--out", default=str(ROOT / "workflows"))

    a = ap.parse_args()
    reg = load_registry()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    if a.cmd == "build":
        try:
            g = build(reg, tier=a.tier, weight=a.weight, attention=a.attention,
                      turbo=a.turbo, mode=a.mode, steps=a.steps, res=a.res,
                      seed=a.seed, prompt=a.prompt,
                      require_identity_fidelity=a.require_identity,
                      allow_4step_ref=a.allow_4step_ref, comfy_version=a.comfy_version,
                      family=a.family, first_frame=a.first_frame, last_frame=a.last_frame,
                      negative_prompt=a.negative_prompt, resolution=a.resolution,
                      spectrum=a.spectrum, cache=a.cache)
        except ValidationError as e:
            print(f"\n✗ 校验失败（不会产出坏工作流）：\n  {e}\n", file=sys.stderr)
            sys.exit(1)
        if a.family == "qwen21":
            name = f"qwen21_setting_{a.resolution or 'default'}_{a.steps or '25'}step.json"
        else:
            name = f"h3_{a.attention}_{a.turbo}_{a.mode}.json"
        p = out / name
        p.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ {p}")

    elif a.cmd == "derive":
        derive(Path(a.src), Path(a.out))

    elif a.cmd == "verify":
        sys.exit(verify(Path(a.workflow), a.host))

    elif a.cmd == "matrix":
        for att in ("sla", "veda", "none"):
            for tb in ("fused", "lora", "none"):
                try:
                    g = build(reg, tier=a.tier, weight=a.weight, attention=att,
                              turbo=tb, mode="t2va", comfy_version="0.38.0")
                    p = out / f"h3_{att}_{tb}.json"
                    p.write_text(json.dumps(g, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
                    print(f"✓ {p.name}")
                except ValidationError as e:
                    print(f"✗ h3_{att}_{tb}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
