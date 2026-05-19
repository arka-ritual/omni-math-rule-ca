#!/usr/bin/env python3
"""Intervention 4 (Wang et al., post-hoc confidence-based scaffolding).

Reads an existing intervention-1 rundir, extracts each instance's last
`submit_confidence` value plus the original patch, applies the τ(λ) rule
from §6 of the paper / §2 of inference/intervention_prompts_swebench.md,
and writes a re-scored rundir whose `preds.json` reflects the
post-hoc decision (submit if confidence ≥ τ, else abstain → empty patch).

τ(λ) defaults:

    +1 / -25  rubric  -> τ = 25/26  ≈ 0.962
    +1 / -100 rubric  -> τ = 100/101 ≈ 0.990
    QP6  / QP7        -> τ = 1.0   (only submit at full confidence)

You can override τ on the command line.

Usage:
    python swebench_pro/scripts/apply_intervention4.py \
        <int1-rundir> <output-rundir> \
        [--tau 0.962] [--prompt-config quant|qp6|qp7] [--rc 1 --ri -25 --ra 0]

If --tau is not provided, it's derived from --prompt-config + the rubric
flags (or the trajectory's stored rubric if available).

Outputs in <output-rundir>:
    preds.json                — instance_id -> {model_name_or_path, instance_id,
                                                 model_patch}; abstained = empty patch
    intervention4_summary.json — per-instance audit:
        {instance_id: {confidence, decision, tau, original_exit_status}}
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def _derive_tau(prompt_config: str, rc, ri, ra) -> float:
    if prompt_config == "quant":
        if rc is None or ri is None or ra is None:
            raise ValueError(
                "quant requires rc/ri/ra; pass --rc/--ri/--ra or rely on "
                "the trajectory's intervention block."
            )
        rc, ri, ra = float(rc), float(ri), float(ra)
        # Break-even: c*rc + (1-c)*ri = ra  =>  c* = (ra - ri) / (rc - ri)
        denom = rc - ri
        if denom == 0:
            return 1.0
        tau = (ra - ri) / denom
        return max(0.0, min(1.0, tau))
    if prompt_config in ("qp6", "qp7"):
        return 1.0
    raise ValueError(f"can't derive tau for prompt_config={prompt_config!r}")


def _last_confidence(traj: dict) -> float | None:
    log = traj.get("info", {}).get("confidence_log") or []
    if not log:
        return None
    last = log[-1]
    val = last.get("confidence") if isinstance(last, dict) else None
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _load_traj(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("int1_rundir", type=Path,
                    help="path to the intervention-1 rundir (must have preds.json + per-instance trajectories)")
    ap.add_argument("output_rundir", type=Path,
                    help="path for the rescored rundir (created if missing)")
    ap.add_argument("--tau", type=float, default=None,
                    help="abstain-iff-confidence-below-tau threshold; if omitted, derived from --prompt-config")
    ap.add_argument("--prompt-config", choices=["quant", "qp6", "qp7"], default=None,
                    help="rubric type (only needed when --tau is omitted)")
    ap.add_argument("--rc", type=float, default=None)
    ap.add_argument("--ri", type=float, default=None)
    ap.add_argument("--ra", type=float, default=None)
    args = ap.parse_args()

    src = args.int1_rundir
    dst = args.output_rundir
    if not (src / "preds.json").exists():
        sys.exit(f"missing: {src / 'preds.json'}")

    src_preds = json.loads((src / "preds.json").read_text())

    # Try to read the intervention block from any trajectory if the user
    # didn't pass an explicit --tau.
    if args.tau is None:
        sample_traj = None
        for iid in src_preds:
            tpath = src / iid / f"{iid}.traj.json"
            sample_traj = _load_traj(tpath)
            if sample_traj is not None:
                break
        if sample_traj is not None and args.prompt_config is None:
            iv = sample_traj.get("info", {}).get("intervention") or {}
            args.prompt_config = iv.get("prompt_config")
            if args.rc is None: args.rc = iv.get("rubric_correct")
            if args.ri is None: args.ri = iv.get("rubric_incorrect")
            if args.ra is None: args.ra = iv.get("rubric_abstain")
        if args.prompt_config is None:
            sys.exit("Couldn't infer --prompt-config from trajectories. Pass it explicitly.")
        tau = _derive_tau(args.prompt_config, args.rc, args.ri, args.ra)
    else:
        tau = float(args.tau)

    print(f"[int4] tau = {tau:.4f}  (prompt_config={args.prompt_config}, rc={args.rc}, ri={args.ri}, ra={args.ra})")

    dst.mkdir(parents=True, exist_ok=True)
    new_preds: dict = {}
    summary: dict = {}

    for iid, entry in src_preds.items():
        traj = _load_traj(src / iid / f"{iid}.traj.json")
        confidence = _last_confidence(traj) if traj else None
        original_exit = (traj or {}).get("info", {}).get("exit_status")
        original_patch = entry.get("model_patch") or ""

        if confidence is None:
            # Edge case: model went straight to finalize/abstain without ever
            # running submit_confidence. Fall back to its own decision.
            decision = "submit" if original_exit == "Submitted" and original_patch else "abstain"
            patch = original_patch if decision == "submit" else ""
            reason = "no_confidence_recorded"
        else:
            if confidence >= tau:
                decision = "submit"
                patch = original_patch
                reason = f"c={confidence:.3f} >= tau={tau:.3f}"
            else:
                decision = "abstain"
                patch = ""
                reason = f"c={confidence:.3f} < tau={tau:.3f}"

        new_preds[iid] = {
            "model_name_or_path": entry.get("model_name_or_path", ""),
            "instance_id": iid,
            "model_patch": patch,
        }
        summary[iid] = {
            "confidence": confidence,
            "decision": decision,
            "tau": tau,
            "original_exit_status": original_exit,
            "reason": reason,
        }

    (dst / "preds.json").write_text(json.dumps(new_preds, indent=2))
    (dst / "intervention4_summary.json").write_text(json.dumps(summary, indent=2))

    n_total = len(new_preds)
    n_submit = sum(1 for s in summary.values() if s["decision"] == "submit")
    n_abstain = n_total - n_submit
    print(f"[int4] {n_submit} submit / {n_abstain} abstain / {n_total} total")
    print(f"[int4] wrote {dst/'preds.json'}")
    print(f"[int4] wrote {dst/'intervention4_summary.json'}")


if __name__ == "__main__":
    main()
