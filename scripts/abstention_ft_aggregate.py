#!/usr/bin/env python3
import argparse
import csv
import glob
import json
import os

PROMPTS = ["standard", "ultra_cautious", "QP4", "QP7", "quant_m25", "quant_m100"]


def read_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def count_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


_KNOWN_METHODS = ["sft_box", "sft", "dpo"]


_KNOWN_BASE_SLUGS = ["gemma4_e2b", "qwen35_9b"]


_KNOWN_TUNE_MODES = ["qlora", "full"]


_KNOWN_RUBRICS = ["quant_m100", "quant_m25", "mix_m25_m100"]


def variant_meta(variant):
    """Parse a variant slug into components.

    New format (preferred):
      {base}_{tune}_{method}_n{N}_{rubric}_k{K}_p{PP}
        e.g. gemma4_e2b_qlora_sft_n1000_quant_m25_k512_p50

    Old format (still supported for legacy results):
      {base}_{method}_n{N}_{rubric}_k{K}
        e.g. gemma4_e2b_sft_n1000_quant_m25_k512   (treated as tune=qlora, p=50)

    Original (untrained baseline):
      {base}_original

    Returns: (base, method, size, rubric, prefix_k, sft_loss_mode, tune, p_abst_pct)
    """
    base = next((s for s in _KNOWN_BASE_SLUGS if variant.startswith(s)), None)
    if base is None:
        raise ValueError(f"Unknown base slug in variant: {variant}")
    if variant == f"{base}_original":
        return base, "original", 0, "none", 0, None, "original", None

    rest = variant[len(base) + 1:]
    tune = next((t for t in _KNOWN_TUNE_MODES if rest.startswith(t + "_")), None)
    if tune is not None:
        rest = rest[len(tune) + 1:]
    else:
        # Legacy slug — pre-tune-mode era; treat as qlora.
        tune = "qlora"

    method = next((m for m in _KNOWN_METHODS if rest.startswith(m + "_")), rest.split("_")[0])
    parts = rest.split("_")

    size = int(next(p[1:] for p in parts if p.startswith("n") and p[1:].isdigit()))
    prefix_k = int(next(p[1:] for p in parts if p.startswith("k") and p[1:].isdigit()))
    rubric = next((r for r in _KNOWN_RUBRICS if r in rest), "quant_m25")

    p_parts = [p[1:] for p in parts if p.startswith("p") and p[1:].isdigit()]
    p_abst_pct = int(p_parts[0]) if p_parts else 50  # legacy default = 50/50

    sft_loss_mode = "box" if method == "sft_box" else ("full" if method == "sft" else None)

    return base, method, size, rubric, prefix_k, sft_loss_mode, tune, p_abst_pct


def metric_path(root, variant, prompt):
    return os.path.join(root, f"{variant}__{prompt}", "cautious_metrics.json")


def cautious_counts(metrics):
    if metrics is None:
        return None, None, None, None, None
    correct = metrics.get("num_correct", metrics.get("correct"))
    abstained = metrics.get("num_abstained", metrics.get("abstained", 0))
    incorrect = metrics.get("num_incorrect")
    if incorrect is None:
        incorrect = sum(metrics.get(k, 0) for k in ["num_incorrect_standard", "num_incorrect_mixed", "num_incorrect_length_cut", "incorrect_standard", "incorrect_mixed", "incorrect"])
    total = metrics.get("num_total", metrics.get("total"))
    attempted_acc = correct / (correct + incorrect) if correct is not None and correct + incorrect > 0 else None
    return correct, incorrect, abstained, total, attempted_acc


def standard_math_acc(root, variant):
    d = os.path.join(root, f"{variant}__standard", "omni-math")
    paths = glob.glob(os.path.join(d, "*metrics.json"))
    m = read_json(paths[0]) if paths else None
    if m is None:
        return None
    acc = m.get("acc", m.get("accuracy"))
    return acc / 100 if acc is not None and acc > 1 else acc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results_dir", default="inference/results/abstention_ft")
    p.add_argument("--output_root", default="evaluation/output/abstention_ft")
    p.add_argument("--summary_csv", default="evaluation/output/abstention_ft/summary.csv")
    p.add_argument("--summary_md", default="evaluation/output/abstention_ft/summary.md")
    p.add_argument("--prompt", default=None, help="If set, only aggregate results for this prompt")
    args = p.parse_args()

    files = sorted(glob.glob(os.path.join(args.results_dir, "*__*.jsonl")))
    if args.prompt:
        files = [f for f in files if os.path.basename(f).endswith(f"__{args.prompt}.jsonl")]
    variants = sorted({os.path.basename(f).split("__", 1)[0] for f in files})
    std_acc = {v: standard_math_acc(args.output_root, v) for v in variants}

    original_acc = {}
    for v in variants:
        base, method, *_ = variant_meta(v)
        if method == "original":
            original_acc[base] = std_acc[v]

    rows, original_utility = [], {}
    for f in files:
        variant, prompt = os.path.basename(f).removesuffix(".jsonl").split("__", 1)
        base, method, size, rubric, prefix_k, sft_loss_mode, tune, p_abst_pct = variant_meta(variant)
        correct, incorrect, abstained, total, attempted_acc = cautious_counts(read_json(metric_path(args.output_root, variant, prompt)))
        total = total or count_jsonl(f)
        utility = None
        if prompt == "quant_m25" and correct is not None:
            utility = (correct - 25 * incorrect) / 99
        if prompt == "quant_m100" and correct is not None:
            utility = (correct - 100 * incorrect) / 99
        if method == "original" and utility is not None:
            original_utility[(base, prompt)] = utility
        rows.append({
            "variant_slug": variant,
            "base_family": base,
            "tune_mode": tune,
            "method": method,
            "sft_loss_mode": sft_loss_mode,
            "train_size": size,
            "train_rubric": rubric,
            "prefix_k": prefix_k,
            "abstention_pct": p_abst_pct,
            "prompt": prompt,
            "correct": correct,
            "incorrect": incorrect,
            "abstained": abstained,
            "total": total,
            "abstention_rate": abstained / total if abstained is not None and total else None,
            "attempted_accuracy": attempted_acc,
            "standard_math_accuracy": std_acc.get(variant),
            "standard_accuracy_drop_vs_original": original_acc.get(base) - std_acc[variant] if original_acc.get(base) is not None and std_acc.get(variant) is not None else None,
            "standard_abstention_rate": None,
            "utility": utility,
        })

    std_abst = {}
    for r in rows:
        if r["prompt"] == "standard":
            std_abst[r["variant_slug"]] = r["abstention_rate"]
    for r in rows:
        r["standard_abstention_rate"] = std_abst.get(r["variant_slug"])
        orig_util = original_utility.get((r["base_family"], r["prompt"]))
        r["utility_improvement_vs_original"] = r["utility"] - orig_util if r["utility"] is not None and orig_util is not None else None
        r["success_standard_accuracy_drop_le_2pp"] = None if r["method"] == "original" else (r["standard_accuracy_drop_vs_original"] is not None and r["standard_accuracy_drop_vs_original"] <= 0.02)
        r["success_standard_abstention_le_1pct"] = None if r["method"] == "original" else (r["standard_abstention_rate"] is not None and r["standard_abstention_rate"] <= 0.01)
        r["success_quant_utility_gt_original"] = None if r["method"] == "original" or r["prompt"] not in {"quant_m25", "quant_m100"} else (r["utility_improvement_vs_original"] is not None and r["utility_improvement_vs_original"] > 0)

    rows.sort(key=lambda r: (r["base_family"], r["tune_mode"], r["method"], r["train_size"], r["train_rubric"], r["prefix_k"], r["abstention_pct"] or 0, PROMPTS.index(r["prompt"])))
    fields = ["variant_slug", "base_family", "tune_mode", "method", "sft_loss_mode", "train_size", "train_rubric", "prefix_k", "abstention_pct", "prompt", "correct", "incorrect", "abstained", "total", "abstention_rate", "attempted_accuracy", "standard_math_accuracy", "standard_accuracy_drop_vs_original", "standard_abstention_rate", "utility", "utility_improvement_vs_original", "success_standard_accuracy_drop_le_2pp", "success_standard_abstention_le_1pct", "success_quant_utility_gt_original"]
    
    os.makedirs(os.path.dirname(args.summary_csv), exist_ok=True)
    with open(args.summary_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with open(args.summary_md, "w", encoding="utf-8") as f:
        f.write("| " + " | ".join(fields) + " |\n")
        f.write("| " + " | ".join(["---"] * len(fields)) + " |\n")
        for r in rows:
            f.write("| " + " | ".join(str(r[k]) for k in fields) + " |\n")
    print(json.dumps({"rows": len(rows), "summary_csv": args.summary_csv}, indent=2))


if __name__ == "__main__":
    main()
