#!/bin/bash
#SBATCH --job-name=unpack_results
#SBATCH --output=unpack_results.%j.%N.out
#SBATCH --error=unpack_results.%j.%N.err
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --account=ccu108
#SBATCH --export=ALL
# Default: 30 min (enough for csv/impl/small). For full huge archive, raise (e.g. 04:00:00) or split by UNPACK_MODE=impl
#SBATCH -t 00:30:00

# =============================================================================
# Expanse policy (instructor + SDSC) — read before use
# =============================================================================
# * Official user guide: https://www.sdsc.edu/systems/expanse/user_guide.html
# * Do not run **computationally heavy** work on the **login** node for more
#   than ~**20 minutes**; use **sbatch** (a compute node) for long I/O.
# * Do not rely on **background** long jobs on the **login** node; submit
#   a proper Slurm job instead and wait for it to complete (squeue, log files).
# * On an **allocated** node, you can use **htop** (or `top`) to see load; pick
#   a modest **--mem** / **-t** so the job does not over-request resources.
# * If unzipping the **whole** archive is too big or too slow, use this script in
#   **parts** via UNPACK_MODE (see below): e.g. **csv** first, then one **impl**
#   per job, instead of UNPACK_MODE=full once.
#
# This script is **intended to run only under Slurm** (sbatch). It will exit
# if SLURM_JOB_ID is missing unless you set FORCE_LOGIN_UNPACK=1 for a *short*
# test (e.g. list mode only) — not for full-tree extraction on the login node.
# =============================================================================
#
# Unpack a team "results_full" (or similar) .zip on Expanse, then record where
# timing_summary.csv and per-run subdirs live for Python plotting.
#
# UNPACK_MODE (default: csv):
#   list  — `unzip -l` only (fast, tiny I/O) to inspect contents; plan next jobs
#   csv   — extract only timing_summary.csv (if present at zip root) — use for
#           plots without touching multi-GB output trees
#   impl  — extract one top-level implementation folder: set UNPACK_IMPL to
#           serial | pth | omp | mpi | hybrid  (run separate jobs per impl)
#   full  — entire archive to UNPACK_DIR (largest; use only if needed, long -t)
#
# Usage:
#   export RESULTS_ZIP=$HOME/results_full.zip
#   export UNPACK_DIR=${SCRATCH}/stencil_heat_data/results_full
#   export UNPACK_MODE=csv
#   sbatch data/slurm_unpack_results.bash
# =============================================================================

set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" && "${FORCE_LOGIN_UNPACK:-0}" != "1" ]]; then
  echo "ERROR: Run with Slurm, not on the login node, e.g.:" >&2
  echo "  export RESULTS_ZIP=/path/to/results_full.zip" >&2
  echo "  export UNPACK_MODE=csv" >&2
  echo "  sbatch data/slurm_unpack_results.bash" >&2
  echo "For a 1-line listing test only, you may:  FORCE_LOGIN_UNPACK=1 UNPACK_MODE=list ... bash data/slurm_unpack_results.bash" >&2
  exit 1
fi
if [[ -z "${SLURM_JOB_ID:-}" && "${FORCE_LOGIN_UNPACK:-0}" == "1" && "${UNPACK_MODE:-list}" == "full" ]]; then
  echo "ERROR: full unpack is not allowed with FORCE_LOGIN_UNPACK. Use sbatch." >&2
  exit 1
fi

cd "${SLURM_SUBMIT_DIR:-.}"

echo "=== Unpack job (Expanse policy: use compute via sbatch; see script header) ==="
echo "Guide: https://www.sdsc.edu/systems/expanse/user_guide.html"
echo "Host:   $(hostname)"
echo "JobID:  ${SLURM_JOB_ID:-local}"
echo "User:   ${USER:-?}"
echo "Date:   $(date -Is)"
echo "PWD:    $(pwd)"
echo "Mode:   ${UNPACK_MODE:-csv}"
echo ""

RESULTS_ZIP="${RESULTS_ZIP:-${1:-$HOME/results_full.zip}}"
UNPACK_DIR="${UNPACK_DIR:-${2:-${SCRATCH:-$PWD}/results_full_unpacked}}"
PLOT_STAGING_DIR="${PLOT_STAGING_DIR:-}"
UNPACK_MODE="${UNPACK_MODE:-csv}"
UNPACK_IMPL="${UNPACK_IMPL:-serial}"

if [[ ! -f "$RESULTS_ZIP" ]]; then
  echo "ERROR: zip not found: $RESULTS_ZIP" >&2
  exit 1
fi

echo "Source zip:  $RESULTS_ZIP"
echo "Unzip to:   $UNPACK_DIR"
echo "Zip size:   $(du -h "$RESULTS_ZIP" | cut -f1)"
echo ""

mkdir -p "$UNPACK_DIR"

do_unzip_list() {
  echo "=== MODE=list: full zip listing (first 200 lines) ==="
  unzip -l "$RESULTS_ZIP" 2>/dev/null | head -200
  echo "..."
  echo "Use this to see paths; then use UNPACK_MODE=csv or impl=... for partial extract."
}

do_unzip_csv() {
  echo "=== MODE=csv: extract timing_summary.csv only (minimal I/O) ==="
  set +e
  unzip -q -o -j "$RESULTS_ZIP" "timing_summary.csv" -d "$UNPACK_DIR" 2>/dev/null
  rc=$?
  set -e
  if [[ $rc -ne 0 || ! -f "$UNPACK_DIR/timing_summary.csv" ]]; then
    echo "Trying non-root path inside zip..."
    set +e
    unzip -q -o "$RESULTS_ZIP" "*/timing_summary.csv" -d "$UNPACK_DIR" 2>/dev/null
    set -e
    if [[ -f "$UNPACK_DIR/timing_summary.csv" ]]; then
      :
    else
      shopt -s nullglob
      found=( "$UNPACK_DIR"/*/timing_summary.csv )
      if [[ ${#found[@]} -ge 1 ]]; then
        cp -f "${found[0]}" "$UNPACK_DIR/timing_summary.csv" 2>/dev/null || true
      else
        echo "WARNING: timing_summary.csv not found in zip; run UNPACK_MODE=list, then try impl or full."
      fi
    fi
  fi
}

do_unzip_impl() {
  echo "=== MODE=impl: one implementation tree (split big jobs into 5 small ones) ==="
  local impl="${UNPACK_IMPL:-serial}"
  case "$impl" in
    serial|pth|omp|mpi|hybrid) ;;
    *) echo "ERROR: UNPACK_IMPL must be serial|pth|omp|mpi|hybrid" >&2; exit 1 ;;
  esac
  echo "Extracting: ${impl}/*"
  if ! unzip -q -o "$RESULTS_ZIP" "${impl}/*" -d "$UNPACK_DIR" 2>/dev/null; then
    echo "Note: if paths differ, run UNPACK_MODE=list and match folder names in the zip."
    exit 1
  fi
}

do_unzip_full() {
  echo "=== MODE=full: entire archive (heaviest; use only if needed) ==="
  echo "If this times out, use UNPACK_MODE=impl and run once per implementation."
  unzip -q -o "$RESULTS_ZIP" -d "$UNPACK_DIR" || {
    echo "unzip failed; check: file $RESULTS_ZIP" >&2
    exit 1
  }
}

case "$UNPACK_MODE" in
  list)  do_unzip_list ;;
  csv)   do_unzip_csv ;;
  impl)  do_unzip_impl ;;
  full)  do_unzip_full ;;
  *)
    echo "ERROR: UNPACK_MODE must be list|csv|impl|full" >&2
    exit 1
    ;;
esac

echo "Done extract step (mode=$UNPACK_MODE)."

# --- Find timing table (for csv/impl/full) ---
TIMING_CSV=""
if [[ -f "$UNPACK_DIR/timing_summary.csv" ]]; then
  TIMING_CSV="$UNPACK_DIR/timing_summary.csv"
else
  TIMING_CSV="$(find "$UNPACK_DIR" -name 'timing_summary.csv' -type f 2>/dev/null | head -1 || true)"
fi

INFO_FILE="${SLURM_SUBMIT_DIR}/unpack_results_info_${SLURM_JOB_ID:-manual}.txt"
{
  echo "unpacked_to=$UNPACK_DIR"
  echo "unpack_mode=$UNPACK_MODE"
  if [[ -n "$TIMING_CSV" && -f "$TIMING_CSV" ]]; then
    echo "timing_summary_csv=$TIMING_CSV"
  else
    echo "timing_summary_csv=NOT_FOUND"
  fi
} | tee "$INFO_FILE"

if [[ "$UNPACK_MODE" != "list" ]]; then
  echo ""
  echo "=== Per-run subdirs (sample) ==="
  find "$UNPACK_DIR" -type d -name 'n*_p*_t*' 2>/dev/null | head -20 || true
  echo ""
  find "$UNPACK_DIR" -name 'output.txt' -type f 2>/dev/null | wc -l | sed 's/^/  output.txt files: /' || true
fi

if [[ -n "$PLOT_STAGING_DIR" && -n "$TIMING_CSV" && -f "$TIMING_CSV" ]]; then
  echo ""
  echo "Staging timing CSV to PLOT_STAGING_DIR"
  mkdir -p "$PLOT_STAGING_DIR"
  cp -f "$TIMING_CSV" "$PLOT_STAGING_DIR/timing_summary_expanse.csv" || true
  echo "Copied: $PLOT_STAGING_DIR/timing_summary_expanse.csv"
else
  if [[ -n "$TIMING_CSV" && -f "$TIMING_CSV" ]]; then
    echo ""
    echo "scp to laptop, e.g.:  scp expanse:'$TIMING_CSV' ."
  fi
fi

if [[ "$UNPACK_MODE" != "list" && -d "$UNPACK_DIR" ]]; then
  echo ""
  du -sh "$UNPACK_DIR" 2>/dev/null || true
fi

echo ""
echo "Wrote: $INFO_FILE"
echo "Monitor jobs:  squeue -u \$USER    (see user guide for htop on compute node via srun if needed)"
echo "=== Finished: $(date -Is) ==="
exit 0
