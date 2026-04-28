#!/usr/bin/env python3
"""
Load timing_summary.csv and build clear, presentation-ready figures.

Design goals (one main idea per output file, large subplots, no log scale):
  • Time vs n          → few representative p values, separate PNGs or 2-panel max
  • Stacked comp/other → one PNG per problem size n (wide single row)
  • Speedup            → one PNG per n (zoomed y-axis so separation is visible)
  • Efficiency         → one PNG per n (ideal efficiency = 1 shown as faint line only)

Calculations unchanged: speedup = T_serial(n,p=1)/T_impl, efficiency = speedup/p.

Usage:
  python plot_timing_figures.py
  python plot_timing_figures.py --speedup-ylim 0.9 1.35 --annotate
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("agg")
import matplotlib.pyplot as plt
import numpy as np

IMPL_ORDER = ["serial", "pth", "omp", "mpi", "hybrid"]
COLORS = {
    "serial": "#333333",
    "pth": "#1f77b4",
    "omp": "#2ca02c",
    "mpi": "#d62728",
    "hybrid": "#9467bd",
}

LW = 2.5
MS = 7


def read_timing_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                {
                    "impl": r["impl"].strip(),
                    "n": int(r["n"]),
                    "p": int(r["p"]),
                    "t": int(r["t"]),
                    "T_overall": float(r["T_overall"]),
                    "T_computation": float(r["T_computation"]),
                    "T_other": float(r["T_other"]),
                }
            )
    return rows


def to_grid(rows: list[dict]) -> dict[tuple[str, int, int], dict]:
    return {(r["impl"], r["n"], r["p"]): r for r in rows}


def serial_baseline_t(grid, n: int) -> float:
    r = grid.get(("serial", n, 1))
    if r is None:
        raise KeyError(f"Missing serial baseline: (serial, n={n}, p=1)")
    return r["T_overall"]


def annotate_points(ax, xs: list, ys: list, fmt: str = "{:.2f}") -> None:
    for x, y in zip(xs, ys):
        ax.text(
            x,
            y,
            fmt.format(y),
            fontsize=8,
            ha="center",
            va="bottom",
            clip_on=True,
        )


def plot_time_vs_n_panel(
    ax,
    grid,
    impls_present: set[str],
    ns: list[int],
    pval: int,
    *,
    annotate: bool,
) -> None:
    s_ns = [n for n in ns if ("serial", n, pval) in grid]
    if s_ns:
        s_times = [grid[("serial", n, pval)]["T_overall"] for n in s_ns]
        ax.plot(
            s_ns,
            s_times,
            "s--",
            color=COLORS["serial"],
            label="serial",
            linewidth=LW,
            markersize=MS,
        )
        if annotate:
            annotate_points(ax, s_ns, s_times)
    for impl in IMPL_ORDER:
        if impl not in impls_present or impl == "serial":
            continue
        n_ok = [n for n in ns if (impl, n, pval) in grid]
        times = [grid[(impl, n, pval)]["T_overall"] for n in n_ok]
        if times:
            ax.plot(
                n_ok,
                times,
                "o-",
                label=impl,
                color=COLORS.get(impl),
                linewidth=LW,
                markersize=MS,
            )
            if annotate:
                annotate_points(ax, n_ok, times)
    ax.set_title(f"T_overall vs n  (p = {pval})", fontsize=12)
    ax.set_ylabel("Time (s)", fontsize=11)
    ax.set_xlabel("Grid size n", fontsize=11)
    ax.set_xticks(ns)
    ax.grid(True, alpha=0.25)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parent / "timing_summary.csv",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "visuals",
    )
    ap.add_argument(
        "--dpi",
        type=int,
        default=150,
    )
    ap.add_argument(
        "--annotate",
        action="store_true",
        help="Label numeric values at each point (can crowd; use for key slides only)",
    )
    ap.add_argument(
        "--speedup-ylim",
        type=float,
        nargs=2,
        metavar=("LO", "HI"),
        default=None,
        help="Fix speedup y-axis, e.g. 0.9 1.35 so differences are visible (linear scale)",
    )
    ap.add_argument(
        "--time-p-values",
        type=int,
        nargs="*",
        default=[1, 16],
        help="Which p panels to plot for time-vs-n (default: 1 and 16 only; reduces clutter)",
    )
    ap.add_argument(
        "--ideal-reference",
        action="store_true",
        help="Also write fig3_speedup_with_ideal_reference_n*.png (same data + y=p line; full scale)",
    )
    args = ap.parse_args()
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_timing_csv(args.csv)
    if not rows:
        print("No rows in CSV; nothing to plot.")
        return 1
    grid = to_grid(rows)
    impls_present = {r["impl"] for r in rows}
    ns = sorted({r["n"] for r in rows})
    ps = sorted({r["p"] for r in rows})
    p_vals_all = [x for x in (1, 2, 4, 8, 16) if x in ps]
    time_panels = [p for p in args.time_p_values if p in ps]
    if not time_panels:
        time_panels = p_vals_all[:2] if len(p_vals_all) >= 2 else p_vals_all

    # ---- Fig 1: Time vs n — at most 2 panels side by side (large) ----
    n_tp = len(time_panels)
    fig1, axes1 = plt.subplots(
        1,
        n_tp,
        figsize=(6.5 * n_tp, 5.5),
        squeeze=False,
        sharey=False,
    )
    for idx, pval in enumerate(time_panels):
        ax = axes1[0][idx]
        plot_time_vs_n_panel(ax, grid, impls_present, ns, pval, annotate=args.annotate)
        ax.legend(loc="best", fontsize=10, framealpha=0.9)
    fig1.suptitle("Total time vs problem size", fontsize=13, y=1.02)
    fig1.tight_layout()
    p1 = out_dir / "fig1_time_vs_problem_size.png"
    fig1.savefig(p1, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig1)
    print("Wrote", p1)

    # ---- Fig 2: one wide stacked-bar figure per n (single row of p columns) ----
    for n in ns:
        fig_w = max(14, 2.8 * len(p_vals_all))
        fig2, axs2 = plt.subplots(
            1,
            len(p_vals_all),
            figsize=(fig_w, 4.2),
            squeeze=False,
            sharey=True,
        )

        def rowget(key):
            r = grid.get(key)
            return r if r is not None else {}

        impls2 = [i for i in IMPL_ORDER if i in impls_present]
        for j_p, pval in enumerate(p_vals_all):
            axb = axs2[0][j_p]
            x0 = np.arange(len(impls2), dtype=float)
            cvals = [rowget((i, n, pval)).get("T_computation", 0) for i in impls2]
            ovals = [rowget((i, n, pval)).get("T_other", 0) for i in impls2]
            if not any(cvals) and not any(ovals):
                axb.set_visible(False)
                continue
            axb.bar(x0, cvals, 0.72, label="T_computation", color="#4c78a8")
            axb.bar(x0, ovals, 0.72, bottom=cvals, label="T_other", color="#f58518")
            axb.set_xticks(x0)
            axb.set_xticklabels(impls2, rotation=15, ha="right", fontsize=10)
            axb.set_title(f"p = {pval}", fontsize=11)
            axb.set_xlabel("Implementation", fontsize=10)
            if j_p == 0:
                axb.set_ylabel("Time (s)", fontsize=11)
            if j_p == 0:
                axb.legend(fontsize=9, loc="upper right")
        fig2.suptitle(
            f"Computation vs overhead (stacked)   —   n = {n}",
            fontsize=13,
            y=1.05,
        )
        fig2.tight_layout()
        p2 = out_dir / f"fig2_stacked_bars_n{n}.png"
        fig2.savefig(p2, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig2)
        print("Wrote", p2)

    # ---- Fig 3: Speedup — one PNG per n (zoomed y); no reference line that flattens story ----
    for n in ns:
        try:
            t_ref = serial_baseline_t(grid, n)
        except KeyError:
            continue
        if t_ref <= 0:
            continue
        fig3, ax3 = plt.subplots(figsize=(8, 5.5))
        for impl in [i for i in IMPL_ORDER if i in impls_present and i != "serial"]:
            xs, ys = [], []
            for pval in ps:
                g2 = grid.get((impl, n, pval))
                if g2:
                    xs.append(pval)
                    ys.append(t_ref / g2["T_overall"])
            if not xs:
                continue
            ax3.plot(
                xs,
                ys,
                "o-",
                label=impl,
                color=COLORS.get(impl),
                linewidth=LW,
                markersize=MS,
            )
            if args.annotate:
                annotate_points(ax3, xs, ys)

        # No horizontal "ideal speedup = p" line here — it would span 1–16 while data ~1.x
        # Optional break-even vs serial only (very faint); omit by default for clarity
        ax3.set_xticks(ps)
        ax3.set_xlabel("p (processes / threads as reported)", fontsize=11)
        ax3.set_ylabel("Speedup vs serial @ same n", fontsize=11)
        ax3.set_title(f"Speedup   (n = {n})", fontsize=13)
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc="best", fontsize=11)

        if args.speedup_ylim is not None:
            lo, hi = args.speedup_ylim
            ax3.set_ylim(lo, hi)
        else:
            yvals = []
            for impl in [i for i in IMPL_ORDER if i in impls_present and i != "serial"]:
                for pval in ps:
                    g2 = grid.get((impl, n, pval))
                    if g2:
                        yvals.append(t_ref / g2["T_overall"])
            if yvals:
                pad = (max(yvals) - min(yvals)) * 0.08 + 0.02
                ax3.set_ylim(min(yvals) - pad, max(yvals) + pad)

        p3 = out_dir / f"fig3_speedup_n{n}.png"
        fig3.savefig(p3, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig3)
        print("Wrote", p3)

    if args.ideal_reference:
        for n in ns:
            try:
                t_ref = serial_baseline_t(grid, n)
            except KeyError:
                continue
            if t_ref <= 0:
                continue
            fig_ref, axr = plt.subplots(figsize=(8, 5))
            ideal_x = list(ps)
            ideal_y = [float(p) for p in ps]
            axr.plot(
                ideal_x,
                ideal_y,
                "k--",
                linewidth=1.5,
                label="Ideal speedup = p",
            )
            for impl in [i for i in IMPL_ORDER if i in impls_present and i != "serial"]:
                xs, ys = [], []
                for pval in ps:
                    g2 = grid.get((impl, n, pval))
                    if g2:
                        xs.append(pval)
                        ys.append(t_ref / g2["T_overall"])
                if xs:
                    axr.plot(
                        xs,
                        ys,
                        "o-",
                        label=impl,
                        color=COLORS.get(impl),
                        linewidth=LW,
                        markersize=MS,
                    )
            axr.set_xticks(ps)
            axr.set_xlabel("p")
            axr.set_ylabel("Speedup")
            axr.set_title(f"Speedup vs ideal reference line   (n = {n})")
            axr.legend(loc="best", fontsize=9)
            axr.grid(True, alpha=0.25)
            pr = out_dir / f"fig3_speedup_with_ideal_reference_n{n}.png"
            fig_ref.savefig(pr, dpi=args.dpi, bbox_inches="tight")
            plt.close(fig_ref)
            print("Wrote", pr)

    # ---- Fig 4: Efficiency — one PNG per n; faint horizontal at η=1 ----
    for n in ns:
        try:
            t_ref = serial_baseline_t(grid, n)
        except KeyError:
            continue
        if t_ref <= 0:
            continue
        fig4, ax4 = plt.subplots(figsize=(8, 5.5))
        all_y: list[float] = []
        for impl in [i for i in IMPL_ORDER if i in impls_present and i != "serial"]:
            xs, ys = [], []
            for pval in ps:
                g2 = grid.get((impl, n, pval))
                if g2 and pval > 0:
                    s = t_ref / g2["T_overall"]
                    eff = s / pval
                    xs.append(pval)
                    ys.append(eff)
                    all_y.extend(ys)
            if xs:
                ax4.plot(
                    xs,
                    ys,
                    "o-",
                    label=impl,
                    color=COLORS.get(impl),
                    linewidth=LW,
                    markersize=MS,
                )
                if args.annotate:
                    annotate_points(ax4, xs, ys)
        ax4.axhline(1.0, color="#888888", linestyle=":", linewidth=1.2, label="η = 1 (ideal)")
        ax4.set_xticks(ps)
        ax4.set_xlabel("p", fontsize=11)
        ax4.set_ylabel("Parallel efficiency (speedup / p)", fontsize=11)
        ax4.set_title(f"Efficiency   (n = {n})", fontsize=13)
        ax4.grid(True, alpha=0.3)
        ax4.legend(loc="best", fontsize=10)
        if all_y:
            lo = 0.0
            hi = min(1.25, max(all_y) * 1.12)
            ax4.set_ylim(lo, hi)
        p4 = out_dir / f"fig4_efficiency_n{n}.png"
        fig4.savefig(p4, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig4)
        print("Wrote", p4)

    print("Done. Outputs in", out_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
