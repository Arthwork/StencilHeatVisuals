#!/bin/bash
#SBATCH --job-name="heat2d_runs"
#SBATCH --output="heat2d_runs.%j.%N.out"
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=16
#SBATCH --cpus-per-task=1
#SBATCH --mem=32GB
#SBATCH --account=ccu108
#SBATCH --export=ALL
#SBATCH -t 01:00:00

set -euo pipefail

# Run with: sbatch from the `code` directory (or ensure SLURM_SUBMIT_DIR is `code`):
#   cd code && sbatch slurm_fnl_prj_batch.bash
cd "${SLURM_SUBMIT_DIR:-.}"

module purge
module load cpu/0.15.4
module load slurm
module load gcc/10.2.0
module load openmpi/4.0.4

echo "Starting 2D Heat Transfer experiments"
echo "Host: $(hostname)"
echo "JobID: ${SLURM_JOB_ID}"
echo "Date: $(date)"
echo ""

module list 2>&1
echo ""

which gcc
which mpicc
which mpirun
echo ""

make clean
make

# Per-assignment layout: keep large run output under `data/`
RESULTS_DIR="../data/runs_${SLURM_JOB_ID}"
mkdir -p "${RESULTS_DIR}"

SUMMARY_CSV="${RESULTS_DIR}/timing_summary.csv"
echo "impl,n,p,t,T_overall,T_computation,T_other" > "${SUMMARY_CSV}"

# =========================
# SET THIS AFTER CALIBRATION
# =========================
TSTEPS=100

# Required experiment sizes
SIZES="5000 10000 20000 40000"
P_LIST="1 2 4 8 16"

# -------------------------
# Helper function
# -------------------------
extract_times () {
    local logfile="$1"
    awk '
    /T_overall/     {overall=$3}
    /T_computation/ {comp=$3}
    /T_other/       {other=$3}
    END {
        printf "%s,%s,%s\n", overall, comp, other
    }' "${logfile}"
}

# -------------------------
# Create input files
# -------------------------
for N in ${SIZES}; do
    INPUT_FILE="${RESULTS_DIR}/input_${N}.txt"
    echo "Generating input for n=${N}"
    ./make-2d "${N}" "${N}" "${INPUT_FILE}"
done

# -------------------------
# SERIAL
# -------------------------
for N in ${SIZES}; do
    for P in ${P_LIST}; do
        RUN_DIR="${RESULTS_DIR}/serial/n${N}_p${P}_t${TSTEPS}"
        mkdir -p "${RUN_DIR}"

        IN_FILE="${RESULTS_DIR}/input_${N}.txt"
        OUT_FILE="${RUN_DIR}/output.txt"
        LOG_FILE="${RUN_DIR}/log.txt"

        echo "Running SERIAL n=${N} p=${P} t=${TSTEPS}"
        ./stencil-2d -t "${TSTEPS}" -i "${IN_FILE}" -o "${OUT_FILE}" -p "${P}" > "${LOG_FILE}" 2>&1

        TIMES=$(extract_times "${LOG_FILE}")
        echo "serial,${N},${P},${TSTEPS},${TIMES}" >> "${SUMMARY_CSV}"
    done
done

# -------------------------
# PTHREADS
# -------------------------
for N in ${SIZES}; do
    for P in ${P_LIST}; do
        RUN_DIR="${RESULTS_DIR}/pth/n${N}_p${P}_t${TSTEPS}"
        mkdir -p "${RUN_DIR}"

        IN_FILE="${RESULTS_DIR}/input_${N}.txt"
        OUT_FILE="${RUN_DIR}/output.txt"
        LOG_FILE="${RUN_DIR}/log.txt"

        echo "Running PTHREADS n=${N} p=${P} t=${TSTEPS}"
        ./stencil-2d-pth -t "${TSTEPS}" -i "${IN_FILE}" -o "${OUT_FILE}" -p "${P}" > "${LOG_FILE}" 2>&1

        TIMES=$(extract_times "${LOG_FILE}")
        echo "pth,${N},${P},${TSTEPS},${TIMES}" >> "${SUMMARY_CSV}"
    done
done

# -------------------------
# OPENMP
# -------------------------
for N in ${SIZES}; do
    for P in ${P_LIST}; do
        RUN_DIR="${RESULTS_DIR}/omp/n${N}_p${P}_t${TSTEPS}"
        mkdir -p "${RUN_DIR}"

        IN_FILE="${RESULTS_DIR}/input_${N}.txt"
        OUT_FILE="${RUN_DIR}/output.txt"
        LOG_FILE="${RUN_DIR}/log.txt"

        echo "Running OPENMP n=${N} p=${P} t=${TSTEPS}"
        export OMP_NUM_THREADS="${P}"
        ./stencil-2d-omp -t "${TSTEPS}" -i "${IN_FILE}" -o "${OUT_FILE}" -p "${P}" > "${LOG_FILE}" 2>&1

        TIMES=$(extract_times "${LOG_FILE}")
        echo "omp,${N},${P},${TSTEPS},${TIMES}" >> "${SUMMARY_CSV}"
    done
done

# -------------------------
# MPI
# -------------------------
for N in ${SIZES}; do
    for P in ${P_LIST}; do
        RUN_DIR="${RESULTS_DIR}/mpi/n${N}_p${P}_t${TSTEPS}"
        mkdir -p "${RUN_DIR}"

        IN_FILE="${RESULTS_DIR}/input_${N}.txt"
        OUT_FILE="${RUN_DIR}/output.txt"
        LOG_FILE="${RUN_DIR}/log.txt"

        echo "Running MPI n=${N} p=${P} t=${TSTEPS}"
        mpirun -np "${P}" ./stencil-2d-mpi -t "${TSTEPS}" -i "${IN_FILE}" -o "${OUT_FILE}" -p "${P}" > "${LOG_FILE}" 2>&1

        TIMES=$(extract_times "${LOG_FILE}")
        echo "mpi,${N},${P},${TSTEPS},${TIMES}" >> "${SUMMARY_CSV}"
    done
done

# -------------------------
# HYBRID
# Here: total p = MPI ranks * OMP threads
# We map your required p values like this:
#   p=1  => 1 rank x 1 thread
#   p=2  => 1 rank x 2 threads
#   p=4  => 2 ranks x 2 threads
#   p=8  => 4 ranks x 2 threads
#   p=16 => 8 ranks x 2 threads
# -------------------------
for N in ${SIZES}; do
    for P in ${P_LIST}; do
        case "${P}" in
            1) MPI_RANKS=1; OMP_THREADS=1 ;;
            2) MPI_RANKS=1; OMP_THREADS=2 ;;
            4) MPI_RANKS=2; OMP_THREADS=2 ;;
            8) MPI_RANKS=4; OMP_THREADS=2 ;;
            16) MPI_RANKS=8; OMP_THREADS=2 ;;
            *) echo "Unsupported hybrid p=${P}"; exit 1 ;;
        esac

        RUN_DIR="${RESULTS_DIR}/hybrid/n${N}_p${P}_t${TSTEPS}"
        mkdir -p "${RUN_DIR}"

        IN_FILE="${RESULTS_DIR}/input_${N}.txt"
        OUT_FILE="${RUN_DIR}/output.txt"
        LOG_FILE="${RUN_DIR}/log.txt"

        echo "Running HYBRID n=${N} p=${P} (${MPI_RANKS} ranks x ${OMP_THREADS} threads) t=${TSTEPS}"
        export OMP_NUM_THREADS="${OMP_THREADS}"
        mpirun -np "${MPI_RANKS}" ./stencil-2d-hybrid -t "${TSTEPS}" -i "${IN_FILE}" -o "${OUT_FILE}" -p "${OMP_THREADS}" > "${LOG_FILE}" 2>&1

        TIMES=$(extract_times "${LOG_FILE}")
        echo "hybrid,${N},${P},${TSTEPS},${TIMES}" >> "${SUMMARY_CSV}"
    done
done

echo ""
echo "Done. Results in ${RESULTS_DIR}"
echo "Summary CSV: ${SUMMARY_CSV}"