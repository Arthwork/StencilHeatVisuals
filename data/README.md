# Final project — data folder plan (QA, experiments, and figures)

This document describes how this repository is organized, what lives under `data/`, and the **end-to-end plan** to satisfy the CSCI 473 “Homework 6 (Final Project)” requirements for **correctness testing**, **performance experiments**, and **plots / visualizations** (including heatmap animations as video).

---

## Team roles, data pipeline, and who provided what

**Why the Expanse teammate and the visuals lead can split work without duplicating the full 100 runs**

- **Performance figures** (time vs `n`, stacked `T_computation` / `T_other`, speedup, efficiency) need **numeric timing fields** and metadata: `T_overall`, `T_computation`, `T_other`, `n`, `p` — usually in **`timing_summary.csv`** and/or per-run **`log.txt`**. Those files are **small** and are the right source for matplotlib. You do **not** need the multi‑gigabyte **`output.txt`** for every run to build those charts.
- **Heatmaps and MP4/GIF-style animations** need **at least one** final (or per-step) **matrix** in the text format the code writes. A **5k×5k** (or smaller) file is enough for good-looking figures; 40k matrices are for timing scale, not always for publishing every pixel.
- So if **`results_full`** (or a team archive of `runs_<jobid>/`) **came from Expanse batch jobs** using `slurm_fnl_prj_batch.bash` (or equivalent), it already contains the **data generation** the report needs: per-run **logs** and **outputs** plus an aggregated **CSV**, without every teammate re-running the cluster.

**This team’s intended split (update names if your roster differs)**

| Responsibility | Owner (typical) | What it produced |
|------------------|-----------------|------------------|
| **Core code** (stencils, `Makefile`, `compare_outputs.py`, batch scripts) | Alim (core + repo) | `code/` programs and Slurm script; reproducible `make` and runs. |
| **Expanse / HPC execution** (calibrate `t` for ~4 min at 40k serial, run the **100** experiments, aggregate timings) | Alim (Expanse runner) | `timing_summary.csv`, per-impl folders with **`log.txt`** and **`output.txt`**, and optionally a zipped **`results_full`** from the cluster. |
| **Visual creation** (parse timing → plots; heatmaps/MP4 from matrix files; report-ready figures) | You (visuals) | `figures/`, Python notebooks/scripts, and captions that cite **`t`**, `n`, `p`, and implementation. **Input data = files Alim provided** (or a subset you unzip locally) — not a second full Expanse campaign unless you are fixing gaps. |
| **Local testing** (optional, your machine) | You (local / QA spot-check) | **Smaller** runs (e.g. **5k** only) to verify **build, scripts, and plotting pipeline**; optional **`compare_outputs.py`** checks at 5k. This **does not replace** the Expanse timing study for the report. |

**What “Alim did most of Expanse / data generation” means in practice** — *if* the delivered archive matches the assignment design:

- He **generated inputs** (or the batch did) for **n = 5k, 10k, 20k, 40k** and ran **all required implementations** at **p = 1, 2, 4, 8, 16** with a **single calibrated `t`**.
- The **`timing_summary.csv` / logs** in that tree are the **authoritative** source for **section 4 / section 7** performance plots, unless a row is missing or an error appears in `log.txt`.
- **You** then **ingest** that data for visuals and, if the team agreed, run **5k-only** local checks to double-check nothing is miswired on your side.

**If** `results_full` is incomplete (e.g. only some `n` or one impl), the team must **rerun the missing** jobs on Expanse; visuals alone cannot invent missing `T_*` data.

---

### Local 5k testing on your own device — what it *ensures* vs what it *does not*

| Local 5k run **can** help you ensure… | It **does not** ensure… |
|----------------------------------------|-------------------------|
| The repo **builds and runs** on your OS/toolchain. | The **report’s** HPC performance numbers: those are valid only from the **same** `t` and the **Expanse** (or agreed) run **environment**. |
| Your **Python + matplotlib (and optional ffmpeg) pipeline** reads matrix files and produces correct-looking plots/MP4. | **Correctness of every parallel result at 10k/20k/40k** unless you also have those `output.txt` and run `compare_outputs.py` against serial. |
| A **`compare_outputs.py` MATCH** for **5k** (serial vs pth, omp, mpi, hybrid) for a few `p` values — a **spot-check** that the **algorithm output** on your build matches, good for **confidence and demos**. | The **same** numeric identity on **Alim’s** binaries vs yours unless you use the **identical** commit and inputs (floating-point can still differ in edge cases, but the team standard is small tolerance). |
| A **faster** iteration loop for debugging *your* visual parameters (colormap, downsampling, MP4 framerate). | **Scaling** behavior: communication overhead at 40k and 16 processes is a **HPC/Expanse** phenomenon; 5k on a laptop is **not** a substitute for those curves. |

**Bottom line:** Re-running **5k only** locally is **valuable** for *your* **visual and tooling QA** and for a **credible** small correctness sample. It does **not** replace the **full-size, full-grid** **timing** data the assignment expects for the **main** charts — that should still come from **Alim’s Expanse (or project) data** as long as it is complete and reviewed.

---

## 1. Folder layout (what we set up)

| Path | Purpose |
|------|--------|
| `code/` | All **core program sources** (`.c`, `common.h`), `Makefile`, `compare_outputs.py`, `run_experiments.sh`, `slurm_fnl_prj_batch.bash`, and the in-repo `README` that explains build and CLI usage. **Build and run from `code/`.** |
| `data/` | **Experiment outputs, timing CSVs, and artifacts for plots** (and this plan). This aligns with the assignment’s submission idea of a `./data` area for example collected data. |
| `presentation/` | **Empty placeholder** for slide exports, video links, and presentation assets. |

`timing_summary.csv` in this directory is an **example / seed** file from a prior run (or teammate batch); your authoritative summary may be `runs_<jobid>/timing_summary.csv` after a fresh Slurm job.

---

## 2. What your runs produce: `log.txt` vs `output.txt`

This matches how the shell scripts in `code/` are written.

- **`output.txt` (per run directory)**  
  - The **final 2D matrix** after `t` time steps, in text form: first line is `rows cols`, then one row of values per line (what `write_matrix_file` in `common.c` writes to `-o`).  
  - Use this file for **correctness checks** (compare against the serial result for the same `n`, `p`, and `t`).

- **`log.txt` (per run directory)**  
  - **Standard output and standard error** of the run (everything *except* the matrix, which is not printed unless debug verbosity is enabled).  
  - Normally includes the **Performance Summary** block: `T_overall`, `T_computation`, `T_other` (as seconds), plus **reported** `n` and `p`.  
  - Use for **parsing timing** and spot-checking errors. The Slurm batch script can aggregate these into `timing_summary.csv` using the same `awk` patterns.

---

## 3. Correctness plan (must match serial for each configuration)

1. **Build** in `code/`: `make` (or `make clean && make` on a cluster).  
2. For each implementation (**serial, pth, omp, mpi, hybrid**) and each **(n, p, t)** you will report, ensure the **output matrix** matches the **serial** output for the **same** input and `t`.  
3. From `code/`, run:  
   `python compare_outputs.py <serial_output.txt> <other_output.txt>`  
   A returned **`MATCH`** means the two files agree within the script’s **1e-6** per-element tolerance. If not, fix the parallel version before trusting speedup plots.  
4. **Start small** (`n` a few hundred or 5000) to debug quickly, then use the full report grid.  
5. **Hybrid** runs use a specific **MPI rank × OpenMP thread** mapping in `slurm_fnl_prj_batch.bash` so that the **reported** `p` (threads/processes) matches the assignment’s table. Prefer that script on Expanse; do not mix it up with the simpler hybrid example in `run_experiments.sh` without checking semantics.

---

## 4. Performance experiment plan (100 runs, one fixed `t`)

| Parameter | Required values (report) |
|----------|---------------------------|
| `n` (grid size) | 5000, 10000, 20000, 40000 |
| `p` | 1, 2, 4, 8, 16 |
| `t` (iterations) | **One value for all runs**, chosen by calibration |

**Calibration (Expanse, serial, 40k, `p = 1`):** increase or decrease `t` until `T_overall` is about **4 minutes** for the **40k** input. Then use **that exact `t`** for **every** other experiment. That run is the longest; minimize wasted cluster time.

**Count:** 4 sizes × 5 values of `p` = **20 runs per implementation** × 5 implementations = **100** experiments (serial + pthreads + OpenMP + MPI + hybrid).

**Measurements** (for each run, from `log` or `timing_summary.csv`):

- `T_overall`  
- `T_computation`  
- `T_other` (= `T_overall - T_computation`, overhead and communication)  
- `n`, `p` as reported by the program

---

## 5. How to run experiments locally (from `code/`)

- **Ad hoc:** build, generate inputs with `./make-2d`, run each `stencil-2d*` with `-i`, `-o`, `-t`, `-p` as in `code/README.md`.  
- **Sweep one implementation:**  
  `./run_experiments.sh <impl> <t> [results_root]`  
  Default `results_root` is **`../data/results`** (inputs and per-run folders land under that tree).

---

## 6. How to run on Expanse (from `code/`)

1. `cd` into `code/`.  
2. Adjust **`TSTEPS`** in `slurm_fnl_prj_batch.bash` to your **calibrated** `t` after 40k serial calibration.  
3. Submit: `sbatch slurm_fnl_prj_batch.bash`  
4. Output layout: per-job data under **`../data/runs_<SLURM_JOB_ID>/`**, with `timing_summary.csv` inside that directory ( Slurm’s stdout goes to `heat2d_runs.*.out` in the submit directory).

**Large archives (Expanse):** if the team has a `results_full` zip, use a **batch** job to unpack on the cluster (I/O- and time-friendly), then copy or point the plotting scripts at `timing_summary.csv` and the `n*_p*_t*/` (per-run) trees.

1. **Upload** `results_full.zip` to your Expanse home or scratch (e.g. `scp` to `~/` or `$SCRATCH`).
2. **Do not** run long / heavy unzips on the **login** node; use **`sbatch`** (see `slurm_unpack_results.bash` header: ~20 min login limit, no long background work, [Expanse user guide](https://www.sdsc.edu/systems/expanse/user_guide.html)).
3. **Prefer a small job first:** set **`UNPACK_MODE`** so you do not always unpack the whole archive at once:
   - `list` — only lists zip contents (planning)
   - `csv` — only extracts `timing_summary.csv` (enough for **plot_timing_figures.py**)
   - `impl` — one of `serial`, `pth`, `omp`, `mpi`, `hybrid` per job (`UNPACK_IMPL=...`) to split I/O
   - `full` — entire tree (use longer `#SBATCH -t` in the script if needed, or use several `impl` jobs instead)

   ```bash
   export RESULTS_ZIP=$HOME/results_full.zip
   export UNPACK_DIR=${SCRATCH}/stencil_heat_data/results_full
   export UNPACK_MODE=csv
   # export PLOT_STAGING_DIR=$HOME/path/to/.../data   # optional
   sbatch data/slurm_unpack_results.bash
   ```

4. **Check** `unpack_results.JOBID.*.out` and `unpack_results_info_<JOBID>.txt` in the submit directory.
5. **Point** `plot_timing_figures.py` at the CSV: `python plot_timing_figures.py --csv /path/to/timing_summary.csv`  
   For heatmaps, `scp` only the zips or `n*_p*_t*/` you need.
6. **Edit the batch file** as needed: `#SBATCH --account=...`, `#SBATCH -t` (shorter for `csv`/`list`, longer only for `full`).

The batch script: `data/slurm_unpack_results.bash`

---

## 7. Figures and analysis (avoid “only line plots”)

Minimum useful figure set the assignment calls out; combine **five** implementations in each comparison where possible.

1. **Time vs problem size** — e.g. fixed `p` or one panel per `p`, curves per implementation, or a **small multiple** layout.  
2. **Stacked bar** — for each (implementation, n, p), stack **T_computation** and **T_other** to show when **overhead / communication** dominates.  
3. **Speedup** — vs serial (or strong scaling) for each model; label hybrid’s `p` definition clearly.  
4. **Efficiency** — e.g. speedup / p (or per implementation’s best interpretation).  
5. ** Heatmaps of the matrix** — at several time steps (or a short **MP4** built from the same frame sequence you would have used for a **GIF**). Raw per-step dumps are only needed if you add a mode to save them; otherwise use saved matrices at selected `t` or a small `t` run for pretty pictures.

**Animation:** the repo uses **GIF** (Pillow) by default in `plot_heatmaps_gif.py` so **ffmpeg is not required**. You can build an **MP4** from the same frames with `ffmpeg` if you prefer. For a “timestep” story without per-iteration dumps, the heatmap script uses **t = 0** (initial `input_5000.txt`) and **t = final** (`output.txt` inside a run zip).

**Scripts in this folder (outputs go to `data/visuals/`)**

| Script | Input | Output |
|--------|--------|--------|
| `plot_timing_figures.py` | `timing_summary.csv` (default: same directory; override with `--csv`) | `fig1/fig2` in `visuals/stacked` and/or `visuals/unstacked`; `fig3/fig4` in `visuals/` |
| `plot_heatmaps_gif.py` | Optional: `--data-root` pointing to `results_full`; reads `input_5000.txt` and by default `serial/n5000_p1_t100.zip` | `fig5_heatmap_final.png`, `fig5_heatmap_evolution.gif` (2+ frames) |

**Install (once):** from this directory, `python -m pip install -r requirements-visuals.txt`  
**Run (from this `data/` directory):**

```bash
python plot_timing_figures.py
python plot_heatmaps_gif.py
```

### `plot_timing_figures.py` layout modes (fig1/fig2)

The timing script now supports **both** prior styles for `fig1` and `fig2`:

- **Stacked layout** (legacy combined style):
  - `fig1`: one multi-panel figure across selected `p` values
  - `fig2`: one figure per `n` with multiple `p` panels
  - Output folder: `data/visuals/stacked/`
- **Unstacked layout** (separate files by `p`):
  - `fig1`: one file per `p` (`fig1_time_vs_problem_size_p*.png`)
  - `fig2`: one file per `(n, p)` (`fig2_stacked_bars_n*_p*.png`)
  - Output folder: `data/visuals/unstacked/`

`fig3_speedup_n*.png` and `fig4_efficiency_n*.png` are still written to `data/visuals/`.

Use:

```bash
# default: generate both stacked and unstacked fig1/fig2
python plot_timing_figures.py

# only stacked fig1/fig2
python plot_timing_figures.py --fig12-layout stacked

# only unstacked fig1/fig2
python plot_timing_figures.py --fig12-layout unstacked
```

If your `results_full` folder is not next to the outer `StencilHeatRun-main` folder, pass e.g.  
`python plot_heatmaps_gif.py --data-root "C:/path/to/results_full"`.

*Note: `timing_summary.csv` must include every row you need for the report. If a row is missing (e.g. incomplete MPI or no hybrid), the figure script only plots what is in the file.*

---

## 8. Suggested work order (QA + visuals lead)

*When the Expanse runner (e.g. Alim) has already produced `results_full` or `runs_*` with `timing_summary.csv` and the per-run logs: **you skip steps 3–4 as an executor** and instead **import, validate completeness, and plot** (steps 5–6). You may still do **local 5k** (see team section above) in parallel for pipeline/correctness spot-checks.*

1. Verify **build** on the target environment (laptop and, if you have access, Expanse).  
2. **Correctness matrix (sample):** serial vs pth, omp, mpi, hybrid for a few `(n, p, t)` — e.g. **5k** on your device with `compare_outputs.py`, and/or trust teammate’s full checks if documented.  
3. **Calibrate `t`** (40k serial, ~4 min on Expanse) — **Expanse runner** if not already done.  
4. **Full 100 runs** — **Expanse runner** if not already in `results_full`; otherwise **ingest** existing outputs into `data/`.  
5. **Parse** timing into one table for matplotlib (from `timing_summary.csv` / `log.txt`).  
6. **Produce** figures 1–5 and the heatmap / **MP4** for the report and presentation (**visuals lead**; data from teammate’s archive unless you regenerate).  
7. **Presentation folder:** add exported PDF, demo commands, and video link if file size is large.

---

## 9. What to hand in (team, cross-check with Moodle)

Align with the course ZIP layout: `code/`, `report/`, `presentation/`, `data/`, and a top-level `README` describing how to run. This repo’s **`code/`** and **`data/`** are meant to line up with that; add `report/` at the project root if your group keeps LaTeX sources there.

Each student’s **individual** PDF: self- and peer-evaluation as required by the assignment.

---

## 10. Quick reference: trust hierarchy

- **Believe correctness** only if `compare_outputs.py` **MATCH**es serial (for the same inputs and `t`).  
- **Believe timings** if `log.txt` (or `timing_summary.csv`) is present and `T_*` match parsed values.  
- **Use** `data/` for anything that is large, shareable, or “figure-ready” so `code/` stays a clean build tree.

---

*This README is the single place in `data/` that records both the folder reorganization and the project execution plan. Update the calibration value `t` and any team-specific paths here as you finalize the runs.*
