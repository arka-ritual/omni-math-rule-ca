#!/usr/bin/env python3
"""Per-question cost + token estimate across the model lineup,
QP7 framing, both Omni-MATH-Rule and SWE-Bench Pro.

For each (model, dataset) pair we read 2 already-completed instances
(the first 2 in the file/dir) and report:
  - input_tokens (sum of prompt_tokens across all API calls for that item)
  - output_tokens (sum of completion_tokens across all API calls)
  - cost (USD) computed from those tokens via litellm.cost_per_token —
    the same rates litellm itself used to populate
    `info.model_stats.instance_cost` in the SWE-Pro trajectories.

For SWE-Pro trajectories we also report litellm's recorded
`instance_cost` as a sanity check; it should match (modulo
cached_tokens / cache_creation pricing nuances).

Cells with no data on disk are left as placeholders. Run the
"missing data" commands at the bottom of the produced markdown to
fill them in (2 questions per model is cheap).
"""
import json
import os
import glob
from pathlib import Path

from litellm.cost_calculator import cost_per_token

REPO = Path(__file__).resolve().parent.parent

# Display name -> dict with:
#   - litellm slug for cost lookup
#   - omni-math invocation: (provider, model_id [, openrouter_subprovider])
#   - swe-pro invocation: litellm slug for run.sh --model
MODELS = [
    # Anthropic models routed via OpenRouter (direct ANTHROPIC_API_KEY rejected
    # at the time of these runs). litellm's *direct* anthropic slug is still
    # used for cost_per_token lookup so the per-1M rates we report are the
    # native anthropic prices; OpenRouter typically adds a small (~5%) markup
    # on top, so the recomputed $ figures should be treated as a lower bound.
    ("Opus 4.7", {
        "litellm": "anthropic/claude-opus-4-7",
        "omnimath": ("openrouter", "anthropic/claude-opus-4.7"),
        "swe": "openrouter/anthropic/claude-opus-4.7",
    }),
    ("Opus 4.6", {
        "litellm": "anthropic/claude-opus-4-6",
        "omnimath": ("openrouter", "anthropic/claude-opus-4.6"),
        "swe": "openrouter/anthropic/claude-opus-4.6",
    }),
    ("Sonnet 4.6", {
        "litellm": "anthropic/claude-sonnet-4-6",
        "omnimath": ("openrouter", "anthropic/claude-sonnet-4.6"),
        "swe": "openrouter/anthropic/claude-sonnet-4.6",
    }),
    ("GPT 5.4", {
        "litellm": "openai/gpt-5.4",
        "omnimath": ("openai", "gpt-5.4"),
        "swe": "openai/gpt-5.4",
    }),
    ("GPT 5.4 Mini", {
        "litellm": "openai/gpt-5.4-mini",
        "omnimath": ("openai", "gpt-5.4-mini"),
        "swe": "openai/gpt-5.4-mini",
    }),
    ("Gemini 3.1 Pro Preview", {
        "litellm": "gemini/gemini-3.1-pro-preview",
        "omnimath": ("openrouter", "google/gemini-3.1-pro-preview"),
        "swe": "openrouter/google/gemini-3.1-pro-preview",
    }),
    ("Haiku 4.5", {
        "litellm": "anthropic/claude-haiku-4-5-20251001",
        "omnimath": ("anthropic", "claude-haiku-4-5"),
        "swe": "anthropic/claude-haiku-4-5",
    }),
    ("GPT 5.4 Nano", {
        "litellm": "openai/gpt-5.4-nano",
        "omnimath": ("openai", "gpt-5.4-nano"),
        "swe": "openai/gpt-5.4-nano",
    }),
    ("Gemini 3 Flash", {
        "litellm": "gemini/gemini-3-flash-preview",
        "omnimath": ("openrouter", "google/gemini-3-flash-preview"),
        "swe": "gemini/gemini-3-flash-preview",
    }),
    ("Gemini 3.1 Flash-Lite", {
        "litellm": "gemini/gemini-3.1-flash-lite-preview",
        "omnimath": ("openrouter", "google/gemini-3.1-flash-lite-preview"),
        "swe": "gemini/gemini-3.1-flash-lite-preview",
    }),
]

# Display name -> path to the QP7 JSONL on the omni-math side.
# Single API call per item; `prompt_tokens` and `completion_tokens` are
# already the per-item totals.
_OM = REPO / "inference/results/interventions"
OMNIMATH_QP7 = {
    "Opus 4.7":              _OM / "anthropic_claude-opus-4.7_int1_QP7.jsonl",
    "Opus 4.6":              _OM / "anthropic_claude-opus-4.6_int1_QP7.jsonl",
    "Sonnet 4.6":            _OM / "anthropic_claude-sonnet-4.6_int1_QP7.jsonl",
    "GPT 5.4":               _OM / "gpt-5.4_int1_QP7.jsonl",
    "GPT 5.4 Mini":          _OM / "gpt-5.4-mini_int1_QP7.jsonl",
    "Gemini 3.1 Pro Preview": _OM / "google_gemini-3.1-pro-preview_int1_QP7.jsonl",
    "Haiku 4.5":             _OM / "claude-haiku-4-5_int1_QP7.jsonl",
    "GPT 5.4 Nano":          _OM / "gpt-5.4-nano_int1_QP7.jsonl",
    "Gemini 3 Flash":        _OM / "google_gemini-3-flash-preview_int1_QP7.jsonl",
    "Gemini 3.1 Flash-Lite": _OM / "gemini-3.1-flash-lite-preview_int1_QP7.jsonl",
}

# Display name -> list of candidate rundirs to try in order. We prefer the
# fresh n=2 rundir from the cost-estimate runs; if that's missing fall back
# to the larger n=100 rundir from the main intervention sweep.
_SWE = REPO / "swebench_pro/results"
def _swe_paths(*candidates):
    return [_SWE / c for c in candidates]
SWE_QP7 = {
    "Opus 4.7":              _swe_paths("openrouter_anthropic_claude-opus-4.7_int1_qp7_n2"),
    "Opus 4.6":              _swe_paths("openrouter_anthropic_claude-opus-4.6_int1_qp7_n2"),
    "Sonnet 4.6":            _swe_paths("openrouter_anthropic_claude-sonnet-4.6_int1_qp7_n2"),
    "GPT 5.4":               _swe_paths("openai_gpt-5.4_int1_qp7_n2"),
    "GPT 5.4 Mini":          _swe_paths("openai_gpt-5.4-mini_int1_qp7_n2"),
    "Gemini 3.1 Pro Preview": _swe_paths("openrouter_google_gemini-3.1-pro-preview_int1_qp7_n2"),
    "Haiku 4.5":             _swe_paths("anthropic_claude-haiku-4-5_int1_qp7_n2",
                                        "anthropic_claude-haiku-4-5_int1_qp7_n100"),
    "GPT 5.4 Nano":          _swe_paths("openai_gpt-5.4-nano_int1_qp7_n2",
                                        "openai_gpt-5.4-nano_int1_qp7_n100"),
    "Gemini 3 Flash":        _swe_paths("gemini_gemini-3-flash-preview_int1_qp7_n2"),
    "Gemini 3.1 Flash-Lite": _swe_paths("gemini_gemini-3.1-flash-lite-preview_int1_qp7_n2",
                                        "gemini_gemini-3.1-flash-lite-preview_int1_qp7_n100"),
}

K = 2  # how many instances to average per cell

# SWE-Pro cells with no real trajectory data on disk for which we want to
# fill the row by interpolation rather than leave as TODO.
#
# Each entry maps target display name -> reference display name. We:
#   1. Read the reference model's average input/output token counts (assumes
#      the target would have a similar token-usage profile if the run had
#      completed normally), and
#   2. Reprice them at the *target* model's per-token rate.
#
# Cost is then scaled accordingly for the litellm $ column too. Rows
# populated this way are flagged with a footnote in the markdown.
SWE_INTERPOLATIONS = {
    # User-requested: gpt-5.4-mini SWE run hit LimitsExceeded with 250 empty
    # responses (model couldn't emit tool calls), so the live run reported
    # $0. Interpolate from GPT 5.4 — its likely behavior had it been able to
    # complete the agent loop. (gpt-5.4-nano has no SWE traj on disk either,
    # so we use only the upper sibling.)
    "GPT 5.4 Mini": {"reference": "GPT 5.4"},
}


def fmt_money(x):
    if x is None:
        return "—"
    return f"${x:0.4f}"


def cost_from_tokens(slug, prompt_t, completion_t):
    if not prompt_t and not completion_t:
        return None
    try:
        ic, oc = cost_per_token(
            model=slug,
            prompt_tokens=int(prompt_t or 0),
            completion_tokens=int(completion_t or 0),
        )
        return ic + oc
    except Exception as e:
        return None


# ---- Omni-MATH side: read first K items, sum tokens, compute cost. ----
def omnimath_cell(name, slug):
    path = OMNIMATH_QP7.get(name)
    if not path or not path.exists():
        return None
    items = []
    with path.open() as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            items.append(json.loads(ln))
            if len(items) >= K:
                break
    if not items:
        return None
    rows = []
    for it in items:
        pt = it.get("prompt_tokens") or 0
        ct = it.get("completion_tokens") or 0
        rows.append((pt, ct, cost_from_tokens(slug, pt, ct)))
    avg_in = sum(r[0] for r in rows) / len(rows)
    avg_out = sum(r[1] for r in rows) / len(rows)
    avg_cost = sum((r[2] or 0) for r in rows) / len(rows)
    return {
        "n": len(rows), "in": avg_in, "out": avg_out, "cost": avg_cost,
        "per_item": rows, "src": str(path.relative_to(REPO)),
    }


# ---- SWE-Pro interpolation: derive a synthetic row from a reference model. ----
def _swe_interpolated_cell(name, slug, all_cells):
    spec = SWE_INTERPOLATIONS.get(name)
    if not spec:
        return None
    ref_name = spec["reference"]
    ref = all_cells.get(ref_name)
    if not ref:
        return None
    avg_in = ref["in"]
    avg_out = ref["out"]
    # Reprice the reference token profile at this model's rates.
    cost = cost_from_tokens(slug, int(round(avg_in)), int(round(avg_out)))
    if cost is None:
        return None
    # Scale the litellm $ column by the same ratio (recomputed_cost
    # ratio); ref's litellm value already accounts for prompt caching, so
    # this carries that mix forward.
    if ref.get("cost"):
        scale = cost / ref["cost"]
    else:
        scale = 1.0
    lit = (ref.get("litellm_cost") or 0.0) * scale
    return {
        "n": ref["n"], "in": avg_in, "out": avg_out,
        "cost": cost, "litellm_cost": lit,
        "per_item": [], "src": f"interpolated from {ref_name} ({ref['src']})",
        "interpolated": True, "ref": ref_name,
    }


# ---- SWE-Pro side: read first K traj files, sum per-call usage. ----
def swe_cell(name, slug):
    candidates = SWE_QP7.get(name) or []
    if not isinstance(candidates, list):
        candidates = [candidates]
    rundir = next((c for c in candidates if c.exists()), None)
    if rundir is None:
        return None
    trajs = sorted(glob.glob(str(rundir / "instance_*" / "instance_*.traj.json")))
    if len(trajs) < 1:
        return None
    trajs = trajs[:K]
    rows = []
    for tp in trajs:
        try:
            t = json.load(open(tp))
        except Exception:
            continue
        in_t = out_t = 0
        for m in t.get("messages", []):
            if m.get("role") != "assistant":
                continue
            extra = m.get("extra") or {}
            usage = ((extra.get("response") or {}).get("usage") or {})
            in_t += int(usage.get("prompt_tokens") or 0)
            out_t += int(usage.get("completion_tokens") or 0)
        litellm_cost = ((t.get("info") or {}).get("model_stats") or {}).get("instance_cost")
        my_cost = cost_from_tokens(slug, in_t, out_t)
        rows.append((in_t, out_t, my_cost, litellm_cost))
    if not rows:
        return None
    avg_in = sum(r[0] for r in rows) / len(rows)
    avg_out = sum(r[1] for r in rows) / len(rows)
    avg_cost = sum((r[2] or 0) for r in rows) / len(rows)
    avg_lit = sum((r[3] or 0) for r in rows) / len(rows)
    return {
        "n": len(rows), "in": avg_in, "out": avg_out,
        "cost": avg_cost, "litellm_cost": avg_lit,
        "per_item": rows, "src": str(rundir.relative_to(REPO)),
    }


def fmt_int(x):
    if x is None:
        return "—"
    return f"{x:,.0f}"


def main():
    out = REPO / "evaluation/output/cost_estimate.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# Per-question cost + token estimate (QP7 framing)")
    lines.append("")
    lines.append(f"Average of the first {K} instances per cell. Costs computed via")
    lines.append("`litellm.cost_per_token` using the same pricing registry that")
    lines.append("populates `info.model_stats.instance_cost` in SWE-Pro trajectories.")
    lines.append("")
    lines.append("- **omni-math**: token counts read directly from")
    lines.append("  `inference/results/interventions/<model>_int1_QP7.jsonl`")
    lines.append("  (single API call per question, QP7 framing in system prompt).")
    lines.append("- **swe-pro**: tokens summed across all assistant turns'")
    lines.append("  `usage.prompt_tokens` / `usage.completion_tokens` in")
    lines.append("  `<rundir>/instance_<id>/instance_<id>.traj.json`.")
    lines.append("  `litellm $` is the value litellm itself recorded in")
    lines.append("  `info.model_stats.instance_cost`; `recomputed $` is what we get")
    lines.append("  from raw token counts × `cost_per_token`. Small disagreements")
    lines.append("  are expected when prompt caching or cache_creation tokens were")
    lines.append("  involved (litellm prices those at a discount).")
    lines.append("")
    lines.append("Per-1M-token rates (from `litellm.cost_per_token`):")
    lines.append("")
    lines.append("| Model | input / 1M | output / 1M |")
    lines.append("|---|---:|---:|")
    for name, info in MODELS:
        try:
            ic, oc = cost_per_token(model=info["litellm"], prompt_tokens=1_000_000, completion_tokens=1_000_000)
            lines.append(f"| {name} | ${ic:0.2f} | ${oc:0.2f} |")
        except Exception:
            lines.append(f"| {name} | (litellm registry miss) | — |")
    lines.append("")

    # ---- Omni-MATH table ----
    lines.append("## Omni-MATH-Rule (QP7, single-call)")
    lines.append("")
    lines.append("| Model | n | input tokens (avg) | output tokens (avg) | cost / question (avg) |")
    lines.append("|---|---:|---:|---:|---:|")
    missing_om = []
    for name, info in MODELS:
        cell = omnimath_cell(name, info["litellm"])
        if cell is None:
            missing_om.append((name, info))
            lines.append(f"| {name} | — | — | — | TODO |")
        else:
            lines.append(
                f"| {name} | {cell['n']} | {fmt_int(cell['in'])} | "
                f"{fmt_int(cell['out'])} | {fmt_money(cell['cost'])} |"
            )
    lines.append("")

    # ---- SWE-Bench Pro table ----
    lines.append("## SWE-Bench Pro (QP7 / int1, full agent loop)")
    lines.append("")
    lines.append("Notes:")
    lines.append("- For Anthropic models, `recomputed $` is a *flat-rate* upper bound — it "
                 "ignores prompt-cache discounts. The `litellm $` column "
                 "(taken straight from `info.model_stats.instance_cost`) accounts for "
                 "cached / cache-creation tokens and is the actual billed amount.")
    lines.append("- Rows marked † are interpolated from a sibling model's token "
                 "usage profile, repriced at this model's per-token rates. The "
                 "live run for that cell either had no recoverable trajectory "
                 "data or hit a degenerate exit (e.g. LimitsExceeded with no "
                 "tool calls). See the source-files block for details.")
    lines.append("")
    lines.append("| Model | n | input tokens (avg) | output tokens (avg) | recomputed $/inst | litellm $/inst |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    missing_swe = []
    swe_cells = {}
    # First pass: real cells.
    for name, info in MODELS:
        cell = swe_cell(name, info["litellm"])
        if cell is not None:
            swe_cells[name] = cell
    # Second pass: assemble rows in order; interpolate where missing.
    for name, info in MODELS:
        cell = swe_cells.get(name)
        if cell is None:
            cell = _swe_interpolated_cell(name, info["litellm"], swe_cells)
            if cell is not None:
                swe_cells[name] = cell  # so source block can reference it
        if cell is None:
            missing_swe.append((name, info))
            lines.append(f"| {name} | — | — | — | TODO | TODO |")
        else:
            tag = "†" if cell.get("interpolated") else ""
            lines.append(
                f"| {name}{tag} | {cell['n']} | {fmt_int(cell['in'])} | "
                f"{fmt_int(cell['out'])} | {fmt_money(cell['cost'])} | "
                f"{fmt_money(cell['litellm_cost'])} |"
            )
    lines.append("")

    # ---- Source files block ----
    lines.append("## Source files (per-question detail)")
    lines.append("")
    for name, info in MODELS:
        oc = omnimath_cell(name, info["litellm"])
        sc = swe_cells.get(name)
        if oc is None and sc is None:
            continue
        lines.append(f"### {name}")
        if oc:
            lines.append(f"- omni-math: `{oc['src']}` — per-item `(in, out, cost)`: " +
                         ", ".join(f"({pi:,}, {po:,}, {fmt_money(pc)})" for pi, po, pc in oc['per_item']))
        if sc:
            if sc.get("interpolated"):
                lines.append(
                    f"- swe-pro:   **interpolated** from {sc['ref']} — repriced "
                    f"that model's avg ({fmt_int(sc['in'])} in, {fmt_int(sc['out'])} out) "
                    f"at {name}'s per-token rate. Live run produced no usable "
                    f"trajectories (model couldn't emit tool calls and hit "
                    f"LimitsExceeded with $0 recorded by litellm)."
                )
            else:
                lines.append(f"- swe-pro:   `{sc['src']}` — per-item `(in, out, recomputed_cost, litellm_cost)`: " +
                             ", ".join(
                                 f"({pi:,}, {po:,}, {fmt_money(pc)}, {fmt_money(pl)})"
                                 for pi, po, pc, pl in sc['per_item']
                             ))
        lines.append("")

    # ---- Missing-data note ----
    if missing_om or missing_swe:
        lines.append("## Filling in missing rows")
        lines.append("")
        lines.append(f"These cells have no QP7 data on disk yet. Each command runs only "
                     f"{K} questions/instances per cell, which is enough to populate the "
                     "averages above when this script is re-run. Provider+model ids are "
                     "best-guesses; double-check them against the live API before kicking "
                     "off.")
        lines.append("")
        if missing_om:
            lines.append("### Omni-MATH-Rule (`inference/run_interventions.py`, "
                         f"int1 / QP7, --num_samples {K}):")
            lines.append("")
            lines.append("```bash")
            for name, info in missing_om:
                provider, model_id, *or_extra = info["omnimath"]
                slug_for_path = model_id.replace("/", "_")
                or_flag = f" --openrouter-provider {or_extra[0]}" if or_extra else ""
                lines.append(f"# {name}")
                lines.append(
                    f"python inference/run_interventions.py \\\n"
                    f"  --provider {provider} --model {model_id} \\\n"
                    f"  --intervention 1 --prompt_config QP7 \\\n"
                    f"  --save_path inference/results/interventions/{slug_for_path}_int1_QP7.jsonl \\\n"
                    f"  --num_samples {K} --seed 100 \\\n"
                    f"  --temperature 1.0 --max_tokens 64000 --concurrency 2"
                    + or_flag
                )
                lines.append("")
            lines.append("```")
            lines.append("")
        if missing_swe:
            lines.append("### SWE-Bench Pro (`swebench_pro/run.sh`, "
                         f"int1 / qp7, --n {K}):")
            lines.append("")
            lines.append("```bash")
            for name, info in missing_swe:
                lines.append(f"# {name}")
                lines.append(
                    f"bash swebench_pro/run.sh \\\n"
                    f"  --model {info['swe']} \\\n"
                    f"  --intervention 1 --prompt-config qp7 \\\n"
                    f"  --n {K} --workers 2 --eval-workers 2 \\\n"
                    f"  --reasoning-effort medium --no-eval"
                )
                lines.append("")
            lines.append("```")
            lines.append("")
        lines.append("After the runs finish, re-run `python scripts/cost_estimate.py` "
                     "to refresh this file.")
        lines.append("")

    out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
