#!/usr/bin/env python3
"""Render the data behind `evaluation/output/cost_estimate.md` as an
Excel workbook for easier sorting / filtering / pivoting.

Reuses the data-loading functions from `scripts/cost_estimate.py` so
the numbers stay in sync; if you change pricing or add models there,
just rerun this script.

Sheets:
  1. Summary       — one row per model, omni-math + swe-pro side by side
  2. Pricing       — per-1M-token rates from litellm
  3. Omni-MATH     — table + per-item breakdown
  4. SWE-Bench Pro — table + per-item breakdown
  5. Notes         — methodology + interpolation footnote
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from litellm.cost_calculator import cost_per_token

import sys
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from cost_estimate import (  # noqa: E402
    MODELS,
    SWE_INTERPOLATIONS,
    omnimath_cell,
    swe_cell,
    _swe_interpolated_cell,
)


# ---- styling ----------------------------------------------------------
HEADER_FILL = PatternFill("solid", fgColor="305496")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
SUBHEAD_FILL = PatternFill("solid", fgColor="D9E1F2")
SUBHEAD_FONT = Font(name="Calibri", size=11, bold=True, color="000000")
INTERP_FILL = PatternFill("solid", fgColor="FFF2CC")
TODO_FILL = PatternFill("solid", fgColor="F8CBAD")
THIN = Side(border_style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")
WRAP = Alignment(horizontal="left", vertical="top", wrap_text=True)


def _style_header_row(ws, row, n_cols):
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER


def _style_subheader_row(ws, row, n_cols):
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = SUBHEAD_FILL
        cell.font = SUBHEAD_FONT
        cell.alignment = LEFT
        cell.border = BORDER


def _autosize(ws, max_width=60, min_width=8):
    for col_cells in ws.columns:
        idx = col_cells[0].column
        letter = get_column_letter(idx)
        longest = 0
        for c in col_cells:
            val = c.value
            if val is None:
                continue
            for line in str(val).splitlines():
                longest = max(longest, len(line))
        ws.column_dimensions[letter].width = min(max(longest + 2, min_width), max_width)


def _money(v):
    return None if v is None else float(v)


# ---- Sheet builders ---------------------------------------------------
def _gather_data():
    pricing = []
    for name, info in MODELS:
        try:
            ic, oc = cost_per_token(model=info["litellm"], prompt_tokens=1_000_000, completion_tokens=1_000_000)
        except Exception:
            ic = oc = None
        pricing.append((name, info["litellm"], ic, oc))

    om_cells = {name: omnimath_cell(name, info["litellm"]) for name, info in MODELS}
    real_swe = {}
    for name, info in MODELS:
        c = swe_cell(name, info["litellm"])
        if c is not None:
            real_swe[name] = c
    swe_cells = {}
    for name, info in MODELS:
        c = real_swe.get(name) or _swe_interpolated_cell(name, info["litellm"], real_swe)
        if c is not None:
            swe_cells[name] = c
    return pricing, om_cells, swe_cells


def build_summary_sheet(wb, pricing, om_cells, swe_cells):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Per-question cost + token estimate (QP7 framing)"
    ws["A1"].font = Font(name="Calibri", size=14, bold=True)
    ws.merge_cells("A1:K1")
    ws["A2"] = "Average of the first 2 instances per cell. Costs computed via litellm.cost_per_token."
    ws["A2"].font = Font(italic=True, color="666666")
    ws.merge_cells("A2:K2")

    # Column groups
    ws.cell(row=4, column=1, value="").value = ""
    ws.cell(row=4, column=2, value="Per-1M token rates")
    ws.merge_cells(start_row=4, start_column=2, end_row=4, end_column=3)
    ws.cell(row=4, column=4, value="Omni-MATH-Rule (single API call)")
    ws.merge_cells(start_row=4, start_column=4, end_row=4, end_column=7)
    ws.cell(row=4, column=8, value="SWE-Bench Pro (full agent loop)")
    ws.merge_cells(start_row=4, start_column=8, end_row=4, end_column=12)
    _style_subheader_row(ws, 4, 12)

    headers = [
        "Model",
        "Input $/1M", "Output $/1M",
        "n", "Input tok (avg)", "Output tok (avg)", "Cost / question",
        "n", "Input tok (avg)", "Output tok (avg)", "Recomputed $/inst", "litellm $/inst",
    ]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=5, column=i, value=h)
    _style_header_row(ws, 5, len(headers))

    pricing_lookup = {name: (ic, oc) for name, _, ic, oc in pricing}

    r = 6
    for name, info in MODELS:
        ic, oc = pricing_lookup.get(name, (None, None))
        oc_cell = om_cells.get(name)
        sc_cell = swe_cells.get(name)
        is_interp = bool(sc_cell and sc_cell.get("interpolated"))

        row = [
            name + ("†" if is_interp else ""),
            _money(ic), _money(oc),
            (oc_cell["n"] if oc_cell else None),
            (oc_cell["in"] if oc_cell else None),
            (oc_cell["out"] if oc_cell else None),
            (_money(oc_cell["cost"]) if oc_cell else None),
            (sc_cell["n"] if sc_cell else None),
            (sc_cell["in"] if sc_cell else None),
            (sc_cell["out"] if sc_cell else None),
            (_money(sc_cell["cost"]) if sc_cell else None),
            (_money(sc_cell["litellm_cost"]) if sc_cell else None),
        ]
        for i, v in enumerate(row, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BORDER
            if i == 1:
                cell.alignment = LEFT
                cell.font = Font(bold=True)
            else:
                cell.alignment = RIGHT
            if i in (2, 3, 7, 11, 12):
                cell.number_format = '"$"#,##0.0000'
            elif i in (5, 6, 9, 10):
                cell.number_format = '#,##0'
            elif i in (4, 8):
                cell.number_format = '0'

        if is_interp:
            for c in range(1, len(headers) + 1):
                ws.cell(row=r, column=c).fill = INTERP_FILL
        elif sc_cell is None:
            # SWE row missing entirely
            for c in range(8, len(headers) + 1):
                ws.cell(row=r, column=c).fill = TODO_FILL
                if ws.cell(row=r, column=c).value is None:
                    ws.cell(row=r, column=c).value = "TODO"
        r += 1

    # Footer notes inline
    r += 1
    ws.cell(row=r, column=1, value="† interpolated row — see Notes sheet.").font = Font(italic=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=12)
    r += 1
    ws.cell(row=r, column=1,
            value="Anthropic recomputed $ is a flat-rate upper bound and ignores prompt-cache "
                  "discounts. litellm $/inst is the actual recorded billed amount.").font = Font(italic=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=12)

    ws.freeze_panes = "B6"
    _autosize(ws)


def build_pricing_sheet(wb, pricing):
    ws = wb.create_sheet("Pricing")
    headers = ["Model", "litellm slug", "Input $/1M tokens", "Output $/1M tokens"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=1, column=i, value=h)
    _style_header_row(ws, 1, len(headers))
    for r, (name, slug, ic, oc) in enumerate(pricing, start=2):
        ws.cell(row=r, column=1, value=name).alignment = LEFT
        ws.cell(row=r, column=2, value=slug).alignment = LEFT
        c3 = ws.cell(row=r, column=3, value=_money(ic))
        c3.alignment = RIGHT; c3.number_format = '"$"#,##0.0000'
        c4 = ws.cell(row=r, column=4, value=_money(oc))
        c4.alignment = RIGHT; c4.number_format = '"$"#,##0.0000'
        for c in range(1, len(headers) + 1):
            ws.cell(row=r, column=c).border = BORDER
    ws.freeze_panes = "B2"
    _autosize(ws)


def build_omnimath_sheet(wb, om_cells):
    ws = wb.create_sheet("Omni-MATH")
    headers = ["Model", "n", "Input tok (avg)", "Output tok (avg)",
               "Cost / question (avg)", "Source file"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=1, column=i, value=h)
    _style_header_row(ws, 1, len(headers))
    r = 2
    for name, info in MODELS:
        c = om_cells.get(name)
        if c is None:
            ws.cell(row=r, column=1, value=name).font = Font(bold=True)
            ws.cell(row=r, column=2, value="—")
            for col in range(1, len(headers) + 1):
                ws.cell(row=r, column=col).border = BORDER
            r += 1
            continue
        ws.cell(row=r, column=1, value=name).font = Font(bold=True)
        ws.cell(row=r, column=2, value=c["n"])
        ws.cell(row=r, column=3, value=c["in"]).number_format = '#,##0'
        ws.cell(row=r, column=4, value=c["out"]).number_format = '#,##0'
        ws.cell(row=r, column=5, value=_money(c["cost"])).number_format = '"$"#,##0.0000'
        ws.cell(row=r, column=6, value=c["src"]).alignment = LEFT
        for col in range(1, len(headers) + 1):
            ws.cell(row=r, column=col).border = BORDER
        r += 1

    # Per-item detail table
    r += 1
    ws.cell(row=r, column=1, value="Per-item detail").font = Font(bold=True, size=12)
    r += 1
    detail_headers = ["Model", "Item #", "Input tokens", "Output tokens", "Cost"]
    for i, h in enumerate(detail_headers, start=1):
        ws.cell(row=r, column=i, value=h)
    _style_header_row(ws, r, len(detail_headers))
    r += 1
    for name, info in MODELS:
        c = om_cells.get(name)
        if c is None:
            continue
        for idx, (pi, po, pc) in enumerate(c["per_item"], start=1):
            ws.cell(row=r, column=1, value=name).font = Font(bold=True)
            ws.cell(row=r, column=2, value=idx)
            ws.cell(row=r, column=3, value=pi).number_format = '#,##0'
            ws.cell(row=r, column=4, value=po).number_format = '#,##0'
            ws.cell(row=r, column=5, value=_money(pc)).number_format = '"$"#,##0.0000'
            for col in range(1, len(detail_headers) + 1):
                ws.cell(row=r, column=col).border = BORDER
            r += 1

    ws.freeze_panes = "B2"
    _autosize(ws)


def build_swe_sheet(wb, swe_cells):
    ws = wb.create_sheet("SWE-Bench Pro")
    headers = ["Model", "n", "Input tok (avg)", "Output tok (avg)",
               "Recomputed $/inst", "litellm $/inst", "Interpolated", "Source"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=1, column=i, value=h)
    _style_header_row(ws, 1, len(headers))
    r = 2
    for name, info in MODELS:
        c = swe_cells.get(name)
        if c is None:
            ws.cell(row=r, column=1, value=name).font = Font(bold=True)
            for col in range(2, len(headers) + 1):
                ws.cell(row=r, column=col, value="TODO").fill = TODO_FILL
            for col in range(1, len(headers) + 1):
                ws.cell(row=r, column=col).border = BORDER
            r += 1
            continue
        is_interp = bool(c.get("interpolated"))
        ws.cell(row=r, column=1, value=name + ("†" if is_interp else "")).font = Font(bold=True)
        ws.cell(row=r, column=2, value=c["n"])
        ws.cell(row=r, column=3, value=c["in"]).number_format = '#,##0'
        ws.cell(row=r, column=4, value=c["out"]).number_format = '#,##0'
        ws.cell(row=r, column=5, value=_money(c["cost"])).number_format = '"$"#,##0.0000'
        ws.cell(row=r, column=6, value=_money(c["litellm_cost"])).number_format = '"$"#,##0.0000'
        ws.cell(row=r, column=7, value="yes" if is_interp else "no").alignment = CENTER
        ws.cell(row=r, column=8, value=c["src"]).alignment = LEFT
        for col in range(1, len(headers) + 1):
            ws.cell(row=r, column=col).border = BORDER
            if is_interp:
                ws.cell(row=r, column=col).fill = INTERP_FILL
        r += 1

    # Per-item detail (skip interpolated rows since they have no per_item)
    r += 1
    ws.cell(row=r, column=1, value="Per-instance detail").font = Font(bold=True, size=12)
    r += 1
    detail_headers = ["Model", "Item #", "Input tokens", "Output tokens",
                      "Recomputed $", "litellm $"]
    for i, h in enumerate(detail_headers, start=1):
        ws.cell(row=r, column=i, value=h)
    _style_header_row(ws, r, len(detail_headers))
    r += 1
    for name, info in MODELS:
        c = swe_cells.get(name)
        if c is None or not c.get("per_item"):
            continue
        for idx, (pi, po, pc, pl) in enumerate(c["per_item"], start=1):
            ws.cell(row=r, column=1, value=name).font = Font(bold=True)
            ws.cell(row=r, column=2, value=idx)
            ws.cell(row=r, column=3, value=pi).number_format = '#,##0'
            ws.cell(row=r, column=4, value=po).number_format = '#,##0'
            ws.cell(row=r, column=5, value=_money(pc)).number_format = '"$"#,##0.0000'
            ws.cell(row=r, column=6, value=_money(pl)).number_format = '"$"#,##0.0000'
            for col in range(1, len(detail_headers) + 1):
                ws.cell(row=r, column=col).border = BORDER
            r += 1

    ws.freeze_panes = "B2"
    _autosize(ws)


def build_notes_sheet(wb, swe_cells):
    ws = wb.create_sheet("Notes")
    notes = [
        ("Methodology", [
            "Average of the first 2 instances per cell. Costs computed via",
            "litellm.cost_per_token using the same pricing registry that",
            "populates info.model_stats.instance_cost in SWE-Pro trajectories.",
        ]),
        ("Omni-MATH-Rule", [
            "Token counts read directly from",
            "inference/results/interventions/<model>_int1_QP7.jsonl",
            "(single API call per question, QP7 framing in system prompt).",
        ]),
        ("SWE-Bench Pro", [
            "Tokens summed across all assistant turns'",
            "usage.prompt_tokens / usage.completion_tokens in",
            "<rundir>/instance_<id>/instance_<id>.traj.json.",
            "",
            "litellm $ is the value litellm itself recorded in",
            "info.model_stats.instance_cost; recomputed $ is what we get",
            "from raw token counts × cost_per_token.",
            "",
            "For Anthropic models, recomputed $ is a flat-rate upper bound — it",
            "ignores prompt-cache discounts. litellm $ accounts for cached /",
            "cache-creation tokens and is the actual billed amount.",
        ]),
        ("Provider routing", [
            "Anthropic models routed via OpenRouter at the time of these runs",
            "because the direct ANTHROPIC_API_KEY in .env was rejected as",
            "invalid x-api-key. The litellm cost-lookup slug stays on direct",
            "Anthropic pricing (per-token rate within ~5% of OpenRouter billing).",
        ]),
        ("Interpolated rows (†)", [
            "Rows marked † in the Summary / SWE-Bench Pro sheets are interpolated",
            "from a sibling model's token usage profile, repriced at this model's",
            "per-token rates. The live run for that cell either had no recoverable",
            "trajectory data or hit a degenerate exit (LimitsExceeded with no",
            "tool calls). Detail per row:",
            "",
        ]),
    ]
    for tgt, spec in SWE_INTERPOLATIONS.items():
        notes[-1][1].append(f"  • {tgt}: interpolated from {spec['reference']}")

    notes.append(("Missing rows (TODO)", [
        "Cells shown as TODO have no QP7 data on disk. To fill them, run the",
        "shell commands at the bottom of evaluation/output/cost_estimate.md",
        "(generated automatically by scripts/cost_estimate.py).",
    ]))

    r = 1
    for title, body in notes:
        ws.cell(row=r, column=1, value=title).font = Font(bold=True, size=12)
        ws.cell(row=r, column=1).fill = SUBHEAD_FILL
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        r += 1
        for line in body:
            cell = ws.cell(row=r, column=1, value=line)
            cell.alignment = WRAP
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
            r += 1
        r += 1

    for col_letter, w in [("A", 80), ("B", 20), ("C", 20), ("D", 20)]:
        ws.column_dimensions[col_letter].width = w


def main():
    pricing, om_cells, swe_cells = _gather_data()

    wb = Workbook()
    # remove default sheet
    wb.remove(wb.active)

    build_summary_sheet(wb, pricing, om_cells, swe_cells)
    build_pricing_sheet(wb, pricing)
    build_omnimath_sheet(wb, om_cells)
    build_swe_sheet(wb, swe_cells)
    build_notes_sheet(wb, swe_cells)

    out = REPO / "evaluation/output/cost_estimate.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
