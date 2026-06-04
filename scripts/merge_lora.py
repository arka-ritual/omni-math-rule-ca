#!/usr/bin/env python3
"""Merge a PEFT LoRA adapter into its base model and save the result.

Strategy: read the *original* safetensors file from the HF cache, apply
`W' = W + scaling * (lora_B @ lora_A)` to the targeted weight matrices, and
write the result with the **identical** key set. This avoids two failure
modes of the naive `peft.merge_and_unload + save_pretrained` path:

1. `save_pretrained` on Gemma4ForConditionalGeneration silently drops the
   k_proj/v_proj/k_norm weights for cross-attention layers 15-34 because
   the HF inference path doesn't touch them. vLLM, however, requires them
   and refuses to load.
2. `merge_and_unload` requires materialising the full base model in GPU/CPU
   memory plus the adapter, then re-shaping the entire state dict.

The output directory is a self-contained HF model that vLLM/transformers can
load via `--model <out_dir>` without any adapter-loading code path. Safe to
call repeatedly in a bash loop — skips work if already merged.

Usage:
  python scripts/merge_lora.py \
      --base_model google/gemma-4-E2B-it \
      --adapter_dir checkpoints/.../epoch-1 \
      --out_dir   checkpoints/.../epoch-1_merged
"""
import argparse
import json
import os
import shutil

import torch
from huggingface_hub import snapshot_download
from safetensors import safe_open
from safetensors.torch import save_file


def find_base_model_dir(base_model: str) -> str:
    """Return a local directory containing the base model's safetensors."""
    if os.path.isdir(base_model):
        return base_model
    return snapshot_download(repo_id=base_model)


def load_adapter_tensors(adapter_dir: str) -> tuple[dict, dict]:
    """Return (config_dict, {target_module_name: {'A': tensor, 'B': tensor}})."""
    with open(os.path.join(adapter_dir, "adapter_config.json")) as f:
        cfg = json.load(f)
    by_module: dict[str, dict[str, torch.Tensor]] = {}
    src = os.path.join(adapter_dir, "adapter_model.safetensors")
    with safe_open(src, framework="pt") as f:
        for key in f.keys():
            # base_model.model.<module>.lora_{A,B}.weight
            assert key.startswith("base_model.model."), key
            inner = key[len("base_model.model."):]
            stem, last = inner.rsplit(".", 1)  # "<module>.lora_X", "weight"
            assert last == "weight", key
            module_name, lora_tag = stem.rsplit(".", 1)
            ab = "A" if lora_tag == "lora_A" else "B"
            by_module.setdefault(module_name, {})[ab] = f.get_tensor(key)
    return cfg, by_module


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model", required=True)
    p.add_argument("--adapter_dir", required=True)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--force", action="store_true",
                   help="Re-merge even if out_dir already looks complete.")
    args = p.parse_args()

    if (not args.force
            and os.path.exists(os.path.join(args.out_dir, "config.json"))
            and (os.path.exists(os.path.join(args.out_dir, "model.safetensors"))
                 or os.path.exists(os.path.join(
                     args.out_dir, "model.safetensors.index.json")))):
        print(f"[merge_lora] skip (already merged): {args.out_dir}")
        return

    os.makedirs(args.out_dir, exist_ok=True)

    base_dir = find_base_model_dir(args.base_model)
    print(f"[merge_lora] base dir: {base_dir}")
    cfg, by_module = load_adapter_tensors(args.adapter_dir)
    r = cfg["r"]
    alpha = cfg["lora_alpha"]
    scaling = alpha / r
    print(f"[merge_lora] adapter targets {len(by_module)} modules, "
          f"r={r} alpha={alpha} scaling={scaling}")

    # Copy all non-weight files (config, tokenizer, generation_config, etc.).
    for fname in os.listdir(base_dir):
        if fname.endswith(".safetensors") or fname.endswith(".safetensors.index.json"):
            continue
        src = os.path.join(base_dir, fname)
        dst = os.path.join(args.out_dir, fname)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(os.path.realpath(src), dst)

    # Enumerate weight shards. Single-shard models (e.g. Gemma 4 E2B) have one
    # `model.safetensors`; large models (e.g. Qwen3.5-9B) are sharded as
    # `model-00001-of-0000N.safetensors` alongside a `model.safetensors.index.json`.
    # The `.index.json` ends in `.json`, so the `.safetensors` filter excludes it.
    shard_files = sorted(
        f for f in os.listdir(base_dir)
        if f.startswith("model") and f.endswith(".safetensors")
    )
    if not shard_files:
        raise RuntimeError(f"No model*.safetensors found in {base_dir}")
    print(f"[merge_lora] {len(shard_files)} shard(s): {shard_files}")

    # Map an adapter module name to its candidate on-disk weight key(s).
    # The adapter records modules under the *in-memory* module path that peft
    # saw at train time, which can differ from the *on-disk* safetensors key by
    # a "language_model." segment: transformers applies a checkpoint-conversion
    # mapping at load time. Concretely, Qwen3.5-9B stores
    # "model.language_model.layers.N..." on disk but exposes
    # "model.layers.N..." in memory (Gemma 4 keeps "language_model" in both).
    # Try the name as-is and with the segment inserted/removed.
    def candidates_for(m: str) -> list[str]:
        variants = [m]
        if ".language_model." in m:
            variants.append(m.replace(".language_model.", ".", 1))
        elif m.startswith("model."):
            variants.append("model.language_model." + m[len("model."):])
        return [v + ".weight" for v in variants]

    # Build a global key -> shard map across ALL shards so adapter module names
    # (e.g. "model.layers.0.self_attn.q_proj") can be resolved regardless of
    # which shard the weight physically lives in.
    key_to_shard: dict[str, str] = {}
    for shard in shard_files:
        with safe_open(os.path.join(base_dir, shard), framework="pt") as f:
            for key in f.keys():
                key_to_shard[key] = shard

    # Resolve each LoRA target module to its base weight key (validated globally).
    target_to_weight_key: dict[str, str] = {}
    missing = []
    for module in by_module.keys():
        for c in candidates_for(module):
            if c in key_to_shard:
                target_to_weight_key[module] = c
                break
        else:
            missing.append(module)

    if missing:
        sample = ", ".join(missing[:5])
        raise RuntimeError(
            f"{len(missing)} LoRA targets not found in base safetensors "
            f"(first 5: {sample}). The base model checkpoint may have a "
            f"different layout than expected.")

    print(f"[merge_lora] resolved {len(target_to_weight_key)} LoRA→base weight mappings")

    # Invert to weight_key -> module, then group the modules to merge per shard.
    weight_key_to_module = {wk: m for m, wk in target_to_weight_key.items()}

    # Stream through each shard, applying LoRA deltas to its own keys only, and
    # write the merged shard out under the identical filename + key set.
    device = "cuda" if torch.cuda.is_available() else "cpu"
    merged_targets = 0
    for shard in shard_files:
        shard_in = os.path.join(base_dir, shard)
        shard_out = os.path.join(args.out_dir, shard)
        new_tensors: dict[str, torch.Tensor] = {}
        shard_merged = 0
        with safe_open(shard_in, framework="pt") as f:
            meta = f.metadata() or {}
            for key in f.keys():
                t = f.get_tensor(key)
                module = weight_key_to_module.get(key)
                if module is not None:
                    A = by_module[module]["A"].to(device=device, dtype=torch.float32)
                    B = by_module[module]["B"].to(device=device, dtype=torch.float32)
                    # peft layout: W is [out, in]; A is [r, in]; B is [out, r];
                    # delta = B @ A → [out, in]
                    W = t.to(device=device, dtype=torch.float32)
                    delta = (B @ A) * scaling
                    W = W + delta
                    t = W.to(dtype=t.dtype).cpu()
                    del A, B, W, delta
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    shard_merged += 1
                new_tensors[key] = t
        print(f"[merge_lora] writing {shard_out} "
              f"({len(new_tensors)} tensors, {shard_merged} merged)")
        save_file(new_tensors, shard_out, metadata=meta)
        merged_targets += shard_merged

    assert merged_targets == len(target_to_weight_key), (
        f"merged {merged_targets} but expected {len(target_to_weight_key)}")
    print(f"[merge_lora] merged {merged_targets} weight matrices total")

    # For multi-shard models, copy the weight index so the output is loadable.
    # Keys and shard filenames are preserved verbatim, so the base index stays valid.
    index_name = "model.safetensors.index.json"
    base_index = os.path.join(base_dir, index_name)
    if os.path.exists(base_index):
        shutil.copy2(os.path.realpath(base_index), os.path.join(args.out_dir, index_name))
        print(f"[merge_lora] copied {index_name}")
    print("[merge_lora] done.")


if __name__ == "__main__":
    main()
