#!/usr/bin/env python3
"""Fix PEFT LoRA adapter keys so vLLM can apply them to Qwen3.5.

Root cause: training uses AutoModelForCausalLM which loads Qwen3_5ForCausalLM
(module paths: model.layers.*), but vLLM loads Qwen3_5ForConditionalGeneration
(module paths: language_model.model.layers.*).

vLLM's hf_to_vllm_mapper maps "model.language_model.*" -> "language_model.model.*",
but PEFT adapter keys (after stripping "base_model.model.") are "model.layers.*" —
no mapper rule matches, so LoRA is silently never applied.

Fix: rename keys so the stripped name is "model.language_model.layers.*", which
the mapper correctly transforms to "language_model.model.layers.*" — matching
vLLM's internal module paths.

  Before: base_model.model.model.layers.0.mlp.down_proj.lora_A.weight
  After:  base_model.model.model.language_model.layers.0.mlp.down_proj.lora_A.weight
"""

import argparse
import os
import shutil

from safetensors import safe_open
from safetensors.torch import save_file

OLD_INFIX = "base_model.model.model.layers."
NEW_INFIX = "base_model.model.model.language_model.layers."


def fix_adapter_keys(src_dir: str, dst_dir: str) -> int:
    """Rename adapter keys and copy all other files. Returns count of renamed keys."""
    os.makedirs(dst_dir, exist_ok=True)

    src_st = os.path.join(src_dir, "adapter_model.safetensors")
    dst_st = os.path.join(dst_dir, "adapter_model.safetensors")

    tensors = {}
    renamed = 0
    with safe_open(src_st, framework="pt") as f:
        for key in f.keys():
            if key.startswith(OLD_INFIX):
                new_key = NEW_INFIX + key[len(OLD_INFIX):]
                renamed += 1
            else:
                new_key = key
            tensors[new_key] = f.get_tensor(key)

    save_file(tensors, dst_st)

    # Copy all other files (config, tokenizer, etc.) unchanged
    for fname in os.listdir(src_dir):
        if fname == "adapter_model.safetensors":
            continue
        src_f = os.path.join(src_dir, fname)
        dst_f = os.path.join(dst_dir, fname)
        if os.path.isfile(src_f):
            shutil.copy2(src_f, dst_f)
        elif os.path.isdir(src_f):
            if os.path.exists(dst_f):
                shutil.rmtree(dst_f)
            shutil.copytree(src_f, dst_f)

    return renamed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adapter_dir", required=True, help="Source PEFT adapter directory")
    p.add_argument("--output_dir", required=True, help="Output directory for fixed adapter")
    p.add_argument("--verify", action="store_true", help="Print key mapping for spot-check")
    args = p.parse_args()

    src_st = os.path.join(args.adapter_dir, "adapter_model.safetensors")
    if not os.path.exists(src_st):
        raise FileNotFoundError(f"No adapter_model.safetensors in {args.adapter_dir}")

    print(f"[fix_lora_keys] {args.adapter_dir} -> {args.output_dir}")
    renamed = fix_adapter_keys(args.adapter_dir, args.output_dir)
    total = len([
        k for k in open(src_st, "rb").read(10000).decode("latin1", errors="ignore").split("\x00")
        if "lora_" in k
    ])  # rough count via header; exact count below
    with safe_open(src_st, framework="pt") as f:
        total = len(list(f.keys()))
    print(f"  Renamed {renamed}/{total} keys")

    if args.verify or renamed > 0:
        dst_st = os.path.join(args.output_dir, "adapter_model.safetensors")
        with safe_open(src_st, framework="pt") as src_f, safe_open(dst_st, framework="pt") as dst_f:
            src_keys = list(src_f.keys())
            dst_keys = list(dst_f.keys())
        # Show first renamed key as spot-check
        changed = [(o, n) for o, n in zip(src_keys, dst_keys) if o != n]
        if changed:
            print(f"  Example rename:")
            print(f"    Before: {changed[0][0]}")
            print(f"    After:  {changed[0][1]}")
    print(f"[fix_lora_keys] Done.")


if __name__ == "__main__":
    main()
