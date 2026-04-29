#!/usr/bin/env python3
"""
Publication-ready heatmaps and GIF for sparse PDE fields.

Key point:
  These stencil fields are usually heavy-tailed: most cells near 0, thin boundary layers hold signal.
  Linear [0,1] normalization is numerically honest but visually uninformative.

This script preserves streaming/downsampling and adds robust visualization strategy:
  - auto norm-mode selection: linear / power / log
  - percentile clipping for stable contrast
  - contour overlays on log_full and edge_zoom variants
  - side-by-side output (full + boundary zoom)
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("agg")
import matplotlib.animation as mplanim
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, Normalize, PowerNorm
import numpy as np
from PIL import Image

# Final_Proj/results_full  (…/StencilHeatRun-main/data → parents: data, StencilHeatRun-main, Final_Proj)
_DEFAULT_RESULTS = Path(__file__).resolve().parent.parent.parent / "results_full"

DPI = 150
FIGSIZE = (10, 6.2)
EPS = 1e-12


def read_matrix_stream_downsample(
    fp, *, max_dim: int
) -> tuple[int, int, np.ndarray]:
    """
    Stream matrix text and downsample while reading to avoid loading full 10k/20k arrays.
    Expects file pointer at beginning of matrix file.
    """
    header = fp.readline()
    if not header:
        raise ValueError("empty matrix stream")
    rows, cols = map(int, header.strip().split())
    step_r = max(1, int(np.ceil(rows / max_dim)))
    step_c = max(1, int(np.ceil(cols / max_dim)))

    # Max-pooling preserves thin hot/cold structures that stride sampling can miss.
    pooled_rows: list[np.ndarray] = []
    row_accum: list[np.ndarray] = []

    for ridx, line in enumerate(fp):
        if ridx >= rows:
            break
        toks = line.strip().split()
        if not toks:
            continue
        vals = np.fromiter((float(x) for x in toks[:cols]), dtype=np.float64)
        if vals.size < cols:
            # Pad short rows safely (should not happen with valid files)
            vals = np.pad(vals, (0, cols - vals.size), mode="constant")
        col_blocks = []
        for c0 in range(0, cols, step_c):
            col_blocks.append(np.max(vals[c0 : c0 + step_c]))
        pooled_col = np.array(col_blocks, dtype=np.float64)
        row_accum.append(pooled_col)
        if len(row_accum) == step_r:
            pooled_rows.append(np.max(np.vstack(row_accum), axis=0))
            row_accum = []

    if row_accum:
        pooled_rows.append(np.max(np.vstack(row_accum), axis=0))

    arr = np.array(pooled_rows, dtype=np.float64)
    return rows, cols, arr


def read_matrix_path(path: Path, *, max_dim: int) -> tuple[int, int, np.ndarray]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = None
            for n in zf.namelist():
                if n.endswith("output.txt"):
                    name = n
                    break
            if not name:
                raise FileNotFoundError("No output.txt in zip: " + str(path))
            with zf.open(name) as f:
                text_fp = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
                return read_matrix_stream_downsample(text_fp, max_dim=max_dim)
    with path.open("r", encoding="utf-8", errors="replace") as fp:
        return read_matrix_stream_downsample(fp, max_dim=max_dim)


def parse_timestep_label(name: str) -> str | None:
    m = re.search(r"_t(\d+)", name)
    if m:
        return f"t={int(m.group(1)):04d}"
    return None


def parse_run_params(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for key in ("n", "p", "t"):
        m = re.search(rf"(?:^|[_-]){key}(\d+)(?:$|[_-])", text)
        if m:
            out[key] = int(m.group(1))
    return out


def build_frame_label(
    *,
    impl: str,
    run_tag: str,
    timestep: str,
    n_orig: int,
    n_ds: int,
    p_val: int | str,
) -> str:
    return (
        f"{impl}/{run_tag} | {timestep} | "
        f"n_orig={n_orig} n_ds={n_ds} p={p_val}"
    )


def downsample(a: np.ndarray, max_dim: int) -> np.ndarray:
    r, c = a.shape
    if r <= max_dim and c <= max_dim:
        return a
    step_r = max(1, r // max_dim)
    step_c = max(1, c // max_dim)
    return a[::step_r, ::step_c]


def summarize_array(arr: np.ndarray) -> dict[str, float]:
    flat = arr.ravel()
    nz = flat[flat > EPS]
    return {
        "min": float(np.min(flat)),
        "max": float(np.max(flat)),
        "mean": float(np.mean(flat)),
        "nz_fraction": float(np.mean(flat > EPS)),
        "q50": float(np.percentile(flat, 50)),
        "q90": float(np.percentile(flat, 90)),
        "q95": float(np.percentile(flat, 95)),
        "q99": float(np.percentile(flat, 99)),
        "q99_5": float(np.percentile(flat, 99.5)),
        "q99_9": float(np.percentile(flat, 99.9)),
        "nz_q1": float(np.percentile(nz, 1)) if nz.size else 0.0,
    }


def resolve_run_artifact(root: Path, impl: str, folder_name: str) -> Path | None:
    """Prefer unpacked .../n5000_p1_t100/output.txt; else .../n5000_p1_t100.zip."""
    z = root / impl / f"{folder_name}.zip"
    out = root / impl / folder_name / "output.txt"
    if out.is_file():
        return out
    if z.is_file():
        return z
    return None


def choose_auto_mode(stats: dict[str, float]) -> str:
    """
    Auto selector:
      - highly sparse / heavy-tail -> log
      - moderately sparse -> power
      - otherwise -> linear
    """
    nz = stats["nz_fraction"]
    q99 = max(stats["q99"], EPS)
    q999 = max(stats["q99_9"], EPS)
    spread = q999 / q99
    if nz < 0.08 or spread > 1e4:
        return "log"
    if nz < 0.30:
        return "power"
    return "linear"


def compute_clip_bounds(
    arrays: list[np.ndarray],
    *,
    hi_pct: float = 99.9,
    lo_nz_pct: float = 1.0,
) -> tuple[float, float]:
    flat = np.concatenate([a.ravel() for a in arrays])
    nz = flat[flat > EPS]
    vmax = float(np.percentile(flat, hi_pct))
    if vmax <= EPS:
        vmax = max(float(np.max(flat)), 1.0)
    if nz.size:
        vmin = float(np.percentile(nz, lo_nz_pct))
    else:
        vmin = EPS
    vmin = max(vmin, EPS)
    if vmax <= vmin:
        vmax = vmin * 10.0
    return vmin, vmax


def build_norm(
    mode: str,
    *,
    vmin: float,
    vmax: float,
    gamma: float,
):
    if mode == "log":
        return LogNorm(vmin=max(vmin, EPS), vmax=max(vmax, vmin * 10.0))
    if mode == "power":
        return PowerNorm(gamma=gamma, vmin=0.0, vmax=max(vmax, EPS))
    return Normalize(vmin=0.0, vmax=1.0)


def draw_field(
    ax: plt.Axes,
    arr: np.ndarray,
    title: str,
    norm: PowerNorm,
    *,
    cmap: str,
    contours: bool,
    colorbar_label: str,
    colorbar: bool = True,
) -> plt.AxesImage:
    """Returns the AxesImage for animation updates."""
    im = ax.imshow(
        arr,
        origin="lower",
        cmap=cmap,
        aspect="equal",
        norm=norm,
        interpolation="nearest",
    )
    ax.set_title(title, fontsize=12)
    ax.set_xlabel("Column index (downsampled)", fontsize=10)
    ax.set_ylabel("Row index (downsampled)", fontsize=10)
    if contours:
        try:
            if isinstance(norm, LogNorm):
                levels = np.geomspace(max(norm.vmin, EPS), max(norm.vmax, norm.vmin * 10), 8)
                cdata = np.ma.masked_less_equal(arr, EPS)
            else:
                levels = np.linspace(norm.vmin, norm.vmax, 8)[1:-1]
                cdata = np.ma.masked_invalid(arr)
            ax.contour(
                cdata,
                levels=levels,
                colors="white",
                linewidths=0.7,
                alpha=0.8,
            )
        except ValueError:
            pass
    if colorbar:
        cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cb.set_label(colorbar_label, fontsize=10)
    return im


def save_variant(
    out_path: Path,
    arr: np.ndarray,
    title: str,
    *,
    cmap: str,
    norm,
    contours: bool,
    zoom: tuple[float, float, float, float] | None = None,
    colorbar_label: str = "Field value",
) -> None:
    """
    zoom = (xmin_frac, xmax_frac, ymin_frac, ymax_frac) in [0,1].
    """
    fig, ax = plt.subplots(figsize=FIGSIZE)
    draw_field(
        ax,
        arr,
        title,
        norm,
        cmap=cmap,
        contours=contours,
        colorbar_label=colorbar_label,
        colorbar=True,
    )
    if zoom is not None:
        xmin_f, xmax_f, ymin_f, ymax_f = zoom
        h, w = arr.shape
        xmin = max(0, int(xmin_f * w))
        xmax = min(w - 1, int(xmax_f * w))
        ymin = max(0, int(ymin_f * h))
        ymax = min(h - 1, int(ymax_f * h))
        if xmax > xmin and ymax > ymin:
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(ymin, ymax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def audit_report(
    out_dir: Path,
    *,
    impl: str,
    run_tag: str,
    correctness_report: Path | None,
    timing_csv: Path | None,
) -> None:
    lines: list[str] = []
    lines.append(f"impl={impl}")
    lines.append(f"run_tag={run_tag}")
    lines.append("")
    lines.append("[correctness]")
    if correctness_report and correctness_report.is_file():
        txt = correctness_report.read_text(encoding="utf-8", errors="replace")
        has_match = "MATCH" in txt
        lines.append(f"correctness_report={correctness_report}")
        lines.append(f"has_MATCH={has_match}")
    else:
        lines.append("correctness_report=missing")
        lines.append("has_MATCH=False")
    lines.append("")
    lines.append("[timing_grid]")
    required_ns = {5000, 10000, 20000, 40000}
    required_ps = {1, 2, 4, 8, 16}
    if timing_csv and timing_csv.is_file():
        rows = list(csv.DictReader(timing_csv.open("r", encoding="utf-8", newline="")))
        combos = {(int(r["n"]), int(r["p"])) for r in rows}
        tvals = {int(r["t"]) for r in rows}
        missing = sorted((n, p) for n in required_ns for p in required_ps if (n, p) not in combos)
        lines.append(f"timing_csv={timing_csv}")
        lines.append(f"rows={len(rows)}")
        lines.append(f"unique_t_values={sorted(tvals)}")
        lines.append(f"single_fixed_t={len(tvals) == 1}")
        lines.append(f"full_grid_5x4_present={len(missing) == 0}")
        lines.append(f"missing_n_p_pairs={missing}")
    else:
        lines.append("timing_csv=missing")
        lines.append("single_fixed_t=False")
        lines.append("full_grid_5x4_present=False")
        lines.append("missing_n_p_pairs=all")
    report = out_dir / f"fig5_rubric_audit_{impl}_{run_tag}.txt"
    report.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", report)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument(
        "--initial",
        type=str,
        default="input_5000.txt",
        help="File under data-root (or absolute path); empty to skip",
    )
    ap.add_argument(
        "--run-tag",
        type=str,
        default="n5000_p8_t1000",
        help="Subfolder or zip stem under impl/ (e.g. n5000_p8_t1000)",
    )
    ap.add_argument("--impl", type=str, default="mpi", help="Implementation folder (default MPI)")
    ap.add_argument(
        "--matrix",
        type=str,
        default=None,
        help="Primary output .txt (path or name under data-root). If set, skips impl/run-tag folder layout.",
    )
    ap.add_argument(
        "--artifact-prefix",
        type=str,
        default="fig5_heatmap",
        help="Base name for final PNG and evolution GIF (e.g. fig5_heatmap_5k_serial).",
    )
    ap.add_argument(
        "--outputs",
        nargs="*",
        type=Path,
        help="Extra matrix paths or zips (in order)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "visuals",
    )
    ap.add_argument(
        "--correctness-report",
        type=Path,
        default=None,
        help="Optional compare_outputs result text file for rubric audit.",
    )
    ap.add_argument(
        "--timing-csv",
        type=Path,
        default=None,
        help="Optional timing summary CSV for full-grid and fixed-t audit.",
    )
    ap.add_argument(
        "--enable-gif",
        action="store_true",
        help="Enable GIF generation. Default is OFF for faster iterative figure tuning.",
    )
    ap.add_argument(
        "--frame-cache-dir",
        type=Path,
        default=None,
        help="Directory for cached frame PNGs. Default: <out-dir>/<artifact-prefix>_frames",
    )
    ap.add_argument(
        "--resume-frames",
        action="store_true",
        help="Skip rendering frame PNGs that already exist in frame cache.",
    )
    ap.add_argument(
        "--export-frame-pngs",
        action="store_true",
        help="Write each frame used in evolution as standalone PNG.",
    )
    ap.add_argument(
        "--band-zoom",
        action="store_true",
        help="Write a single boundary-band zoom PNG for quick data-throughput visibility.",
    )
    ap.add_argument(
        "--band-frac",
        type=float,
        default=0.08,
        help="Horizontal fraction [0,1] for boundary band zoom width (default 0.08).",
    )
    ap.add_argument("--max-dim", type=int, default=133)
    ap.add_argument("--fps", type=float, default=0.5)
    ap.add_argument(
        "--gamma",
        type=float,
        default=0.35,
        help="PowerNorm gamma (used when norm-mode=power)",
    )
    ap.add_argument(
        "--cmap",
        type=str,
        default="inferno",
        help="Colormap for all outputs",
    )
    ap.add_argument(
        "--no-contours",
        action="store_true",
        help="Disable contour lines",
    )
    ap.add_argument(
        "--multi-fix",
        action="store_true",
        help="Generate multiple diagnostic/fix PNG variants and a stats report",
    )
    ap.add_argument(
        "--norm-mode",
        choices=["auto", "linear", "power", "log"],
        default="linear",
        help="Normalization strategy for primary PNG/GIF.",
    )
    args = ap.parse_args()

    root = args.data_root or _DEFAULT_RESULTS
    if not root.is_dir():
        print("Data root not found:", root)
        print("Expected:", _DEFAULT_RESULTS)
        return 1

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    main_src: Path | None = None
    if args.matrix:
        mp = Path(args.matrix)
        if mp.is_file():
            main_src = mp
        else:
            cand = root / args.matrix
            if cand.is_file():
                main_src = cand
        if main_src is None:
            print("Primary matrix not found:", args.matrix)
            return 1
    else:
        main_src = resolve_run_artifact(root, args.impl, args.run_tag)
        if main_src is None:
            print(
                "Could not find output for",
                root / args.impl / args.run_tag,
                "(need output.txt or .zip, or pass --matrix)",
            )
            return 1

    run_params = parse_run_params(args.run_tag)
    frames_data: list[tuple[np.ndarray, str, int, int]] = []

    if args.initial:
        init_path = Path(args.initial)
        if not init_path.is_file():
            init_path = root / args.initial
        if init_path.is_file():
            r0, c0, a0 = read_matrix_path(init_path, max_dim=args.max_dim)
            frames_data.append(
                (
                    a0,
                    build_frame_label(
                        impl=args.impl,
                        run_tag=args.run_tag,
                        timestep="t=0000",
                        n_orig=r0,
                        n_ds=a0.shape[0],
                        p_val=run_params.get("p", "?"),
                    ),
                    r0,
                    c0,
                )
            )
        else:
            print("Warning: initial not found:", init_path)

    rf, cf, af = read_matrix_path(main_src, max_dim=args.max_dim)
    if "n" not in run_params:
        run_params["n"] = rf
    t_main = parse_timestep_label(main_src.name if hasattr(main_src, "name") else str(main_src))
    frames_data.append(
        (
            af,
            build_frame_label(
                impl=args.impl,
                run_tag=args.run_tag,
                timestep=(t_main or (f"t={int(run_params['t']):04d}" if 't' in run_params else "t=?")),
                n_orig=rf,
                n_ds=af.shape[0],
                p_val=run_params.get("p", "?"),
            ),
            rf,
            cf,
        )
    )

    for extra in args.outputs or []:
        ex = extra if extra.is_file() else root / extra
        if ex.is_file():
            rx, cx, axm = read_matrix_path(ex, max_dim=args.max_dim)
            t_lbl = parse_timestep_label(ex.name) or "t=?"
            frames_data.append(
                (
                    axm,
                    build_frame_label(
                        impl=args.impl,
                        run_tag=args.run_tag,
                        timestep=t_lbl,
                        n_orig=rx,
                        n_ds=axm.shape[0],
                        p_val=run_params.get("p", "?"),
                    ),
                    rx,
                    cx,
                )
            )
        else:
            print("Skip missing:", ex)

    if not frames_data:
        print("No frames.")
        return 1

    arrays = [f[0] for f in frames_data]
    stats = summarize_array(arrays[-1])
    selected_mode = args.norm_mode
    if selected_mode == "auto":
        selected_mode = choose_auto_mode(stats)
    vmin_clip, vmax_clip = compute_clip_bounds(arrays, hi_pct=99.9, lo_nz_pct=1.0)
    norm = build_norm(selected_mode, vmin=vmin_clip, vmax=vmax_clip, gamma=args.gamma)
    label = f"Field value ({selected_mode} norm, clipped; raw unchanged)"

    # Static PNG — last frame (usually equilibrated field)
    fig, ax = plt.subplots(figsize=FIGSIZE)
    draw_field(
        ax,
        frames_data[-1][0],
        frames_data[-1][1],
        norm,
        cmap=args.cmap,
        contours=not args.no_contours,
        colorbar_label=label,
        colorbar=True,
    )
    fig.suptitle(
        (
            "2D heat stencil — temperature field "
            f"(orig n={frames_data[-1][2]}, ds n={frames_data[-1][0].shape[0]}, "
            f"max_dim={args.max_dim}, impl={args.impl}, p={run_params.get('p', '?')})"
        ),
        fontsize=13,
        y=0.98,
    )
    fig.tight_layout()
    png = out_dir / f"{args.artifact_prefix}_final.png"
    fig.savefig(png, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", png)
    print(
        f"  Data range (last frame): min={frames_data[-1][0].min():.6f} max={frames_data[-1][0].max():.6f}"
    )
    print(
        "  Quantiles (last frame): "
        f"q50={stats['q50']:.6f} q95={stats['q95']:.6f} q99={stats['q99']:.6f} "
        f"q99.5={stats['q99_5']:.6f} q99.9={stats['q99_9']:.6f} nz={stats['nz_fraction']:.6f}"
    )
    print(f"  Norm mode selected: {selected_mode} (vmin={vmin_clip:.3e}, vmax={vmax_clip:.3e})")

    # Optional boundary-band quicklook for "is data flowing?" checks.
    if args.band_zoom:
        band_w = max(5, int(frames_data[-1][0].shape[1] * max(0.01, min(args.band_frac, 1.0))))
        save_variant(
            out_dir / f"{args.artifact_prefix}_band_zoom.png",
            frames_data[-1][0],
            f"Boundary band zoom ({int(100 * args.band_frac)}%) — {args.impl}/{args.run_tag}",
            cmap=args.cmap,
            norm=norm,
            contours=not args.no_contours,
            zoom=(0.0, max(0.01, min(args.band_frac, 1.0)), 0.0, 1.0),
            colorbar_label=label,
        )

    if args.multi_fix:
        last_arr = frames_data[-1][0]
        prefix = f"{args.artifact_prefix}_{args.run_tag}_{args.impl}"

        # 1) linear reference
        save_variant(
            out_dir / f"{prefix}_linear_reference.png",
            last_arr,
            f"Linear reference [0,1] — {args.impl}/{args.run_tag}",
            cmap=args.cmap,
            norm=Normalize(vmin=0.0, vmax=1.0),
            contours=False,
            colorbar_label="Field value (linear [0,1])",
        )

        # 2) log full-domain (primary sparse-field fix)
        log_full_norm = build_norm("log", vmin=vmin_clip, vmax=vmax_clip, gamma=args.gamma)
        save_variant(
            out_dir / f"{prefix}_log_full.png",
            last_arr,
            f"LogNorm full domain — {args.impl}/{args.run_tag}",
            cmap=args.cmap,
            norm=log_full_norm,
            contours=not args.no_contours,
            colorbar_label="Field value (LogNorm clipped)",
        )

        # 3) edge zoom (left 5%), tighter clipping
        edge_band = last_arr[:, : max(5, int(last_arr.shape[1] * 0.05))]
        edge_vals = edge_band[edge_band > EPS]
        edge_vmin = float(np.percentile(edge_vals, 1)) if edge_vals.size else EPS
        edge_vmax = float(np.percentile(edge_vals, 99.5)) if edge_vals.size else max(vmax_clip, 1.0)
        edge_norm = build_norm("log", vmin=edge_vmin, vmax=edge_vmax, gamma=args.gamma)
        save_variant(
            out_dir / f"{prefix}_edge_zoom.png",
            last_arr,
            f"Boundary layer zoom (left 5%) — {args.impl}/{args.run_tag}",
            cmap=args.cmap,
            norm=edge_norm,
            contours=not args.no_contours,
            zoom=(0.0, 0.05, 0.0, 1.0),
            colorbar_label="Field value (edge LogNorm)",
        )

        # 4) interior contrast (non-boundary only)
        interior = last_arr.copy()
        interior[0, :] = np.nan
        interior[-1, :] = np.nan
        interior[:, 0] = np.nan
        interior[:, -1] = np.nan
        valid = interior[np.isfinite(interior) & (interior > EPS)]
        ivmin = float(np.percentile(valid, 1)) if valid.size else EPS
        ivmax = float(np.percentile(valid, 99.5)) if valid.size else max(vmax_clip, 1.0)
        interior_norm = build_norm("log", vmin=ivmin, vmax=ivmax, gamma=args.gamma)
        save_variant(
            out_dir / f"{prefix}_interior_contrast.png",
            np.nan_to_num(interior, nan=0.0),
            f"Interior contrast (boundaries removed) — {args.impl}/{args.run_tag}",
            cmap=args.cmap,
            norm=interior_norm,
            contours=False,
            colorbar_label="Interior field value (LogNorm)",
        )

        # 5) side-by-side publication view (shared cmap/norm)
        fig_s, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(14, 5.8), constrained_layout=True)
        draw_field(
            ax_l,
            last_arr,
            "Full Field (Log Scale)",
            log_full_norm,
            cmap=args.cmap,
            contours=not args.no_contours,
            colorbar_label="Field value",
            colorbar=False,
        )
        draw_field(
            ax_r,
            last_arr,
            "Boundary Layer Zoom",
            edge_norm,
            cmap=args.cmap,
            contours=not args.no_contours,
            colorbar_label="Field value",
            colorbar=False,
        )
        ax_r.set_xlim(0, int(last_arr.shape[1] * 0.05))
        cb = fig_s.colorbar(
            ax_l.images[0], ax=[ax_l, ax_r], fraction=0.03, pad=0.02
        )
        cb.set_label("Field value (LogNorm, clipped)")
        fig_s.suptitle(f"{args.impl}/{args.run_tag} — full + edge zoom", fontsize=13)
        fig_s.savefig(out_dir / f"{prefix}_side_by_side.png", dpi=DPI, bbox_inches="tight")
        plt.close(fig_s)

        report = out_dir / f"{prefix}_diagnostics.txt"
        report.write_text(
            "\n".join(
                [
                    f"impl={args.impl}",
                    f"run_tag={args.run_tag}",
                    f"shape={last_arr.shape}",
                    f"min={stats['min']:.10f}",
                    f"max={stats['max']:.10f}",
                    f"mean={stats['mean']:.10f}",
                    f"nonzero_fraction={stats['nz_fraction']:.10f}",
                    f"q50={stats['q50']:.10f}",
                    f"q90={stats['q90']:.10f}",
                    f"q95={stats['q95']:.10f}",
                    f"q99={stats['q99']:.10f}",
                    f"q99.5={stats['q99_5']:.10f}",
                    f"q99.9={stats['q99_9']:.10f}",
                    f"auto_norm_selected={choose_auto_mode(stats)}",
                    f"selected_norm_mode={selected_mode}",
                    f"norm_vmin={vmin_clip:.10e}",
                    f"norm_vmax={vmax_clip:.10e}",
                ]
            ),
            encoding="utf-8",
        )
        print("Wrote", report)

    audit_report(
        out_dir,
        impl=args.impl,
        run_tag=args.run_tag,
        correctness_report=args.correctness_report,
        timing_csv=args.timing_csv,
    )

    # Frame cache: timeout-safe and resumable.
    frame_cache_dir = args.frame_cache_dir or (out_dir / f"{args.artifact_prefix}_frames")
    need_frames_for_gif = args.enable_gif and len(frames_data) > 1
    should_write_frame_cache = args.export_frame_pngs or need_frames_for_gif
    if should_write_frame_cache:
        frame_cache_dir.mkdir(parents=True, exist_ok=True)
        for i, (arr_i, label_i, _, _) in enumerate(frames_data):
            fp = frame_cache_dir / f"frame_{i:03d}.png"
            if args.resume_frames and fp.is_file():
                continue
            fig_f, ax_f = plt.subplots(figsize=FIGSIZE)
            draw_field(
                ax_f,
                np.maximum(arr_i, EPS) if isinstance(norm, LogNorm) else arr_i,
                label_i,
                norm,
                cmap=args.cmap,
                contours=not args.no_contours,
                colorbar_label=label,
                colorbar=True,
            )
            fig_f.tight_layout()
            fig_f.savefig(fp, dpi=DPI, bbox_inches="tight")
            plt.close(fig_f)
            print("Wrote", fp)

    if len(frames_data) == 1 or not args.enable_gif:
        if not args.enable_gif:
            print("GIF disabled by default (--enable-gif to generate).")
        else:
            print("Single frame; no GIF.")
        return 0

    # Build GIF from cached PNG frames (resume-friendly: rerun only missing frames).
    gif_path = out_dir / f"{args.artifact_prefix}_evolution.gif"
    frame_files = [frame_cache_dir / f"frame_{i:03d}.png" for i in range(len(frames_data))]
    missing = [str(p) for p in frame_files if not p.is_file()]
    if missing:
        print("GIF build failed: missing cached frames:", missing[:3], "..." if len(missing) > 3 else "")
        return 1
    try:
        images = [Image.open(fp).convert("P", palette=Image.ADAPTIVE) for fp in frame_files]
        duration_ms = int(round(1000.0 / max(args.fps, 0.1)))
        images[0].save(
            gif_path,
            save_all=True,
            append_images=images[1:],
            duration=duration_ms,
            loop=0,
            optimize=False,
            disposal=2,
        )
    except Exception as e:
        print("GIF save failed:", e)
        return 1
    print("Wrote", gif_path, f"({len(frames_data)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
