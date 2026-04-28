#!/bin/bash
set -euo pipefail

# Usage:
#   ./run_experiments.sh <impl> <t> <results_root>
#
# impl: serial | pth | omp | mpi | hybrid
# t   : fixed number of iterations chosen from your 40k/p=1 calibration
# results_root defaults to ../data/results (run this script from the `code` directory)

impl="${1:-serial}"
t="${2:-100}"
results_root="${3:-../data/results}"

sizes=(5000 10000 20000 40000)
plist=(1 2 4 8 16)

mkdir -p "${results_root}/${impl}"

for n in "${sizes[@]}"; do
  input_dir="${results_root}/inputs"
  mkdir -p "${input_dir}"
  in_file="${input_dir}/input_${n}.txt"

  if [[ ! -f "${in_file}" ]]; then
    ./make-2d "${n}" "${n}" "${in_file}"
  fi

  for p in "${plist[@]}"; do
    run_dir="${results_root}/${impl}/n${n}_p${p}_t${t}"
    mkdir -p "${run_dir}"

    out_file="${run_dir}/output.txt"
    log_file="${run_dir}/log.txt"

    case "${impl}" in
      serial)
        ./stencil-2d -t "${t}" -i "${in_file}" -o "${out_file}" -p "${p}" > "${log_file}" 2>&1
        ;;
      pth)
        ./stencil-2d-pth -t "${t}" -i "${in_file}" -o "${out_file}" -p "${p}" > "${log_file}" 2>&1
        ;;
      omp)
        ./stencil-2d-omp -t "${t}" -i "${in_file}" -o "${out_file}" -p "${p}" > "${log_file}" 2>&1
        ;;
      mpi)
        mpirun -np "${p}" ./stencil-2d-mpi -t "${t}" -i "${in_file}" -o "${out_file}" -p "${p}" > "${log_file}" 2>&1
        ;;
      hybrid)
        # Example policy: p MPI ranks and 2 OMP threads per rank
        OMP_NUM_THREADS=2 mpirun -np "${p}" ./stencil-2d-hybrid -t "${t}" -i "${in_file}" -o "${out_file}" -p 2 > "${log_file}" 2>&1
        ;;
      *)
        echo "Unknown impl: ${impl}"
        exit 1
        ;;
    esac
  done
done
