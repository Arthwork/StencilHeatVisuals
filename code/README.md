# 2D Heat Transfer Project

All build commands in this file assume you are in this **`code/`** directory. The parent folder has **`../data/README.md`**, which is the team’s **experiment, QA, and figure plan**; per-run and bulk outputs go under **`../data/`** by default.

This zip includes:

- `make-2d.c`
- `print-2d.c`
- `stencil-2d.c` (serial)
- `stencil-2d-pth.c` (Pthreads)
- `stencil-2d-omp.c` (OpenMP)
- `stencil-2d-mpi.c` (MPI using `MPI_Sendrecv` and `MPI_Gatherv`/scatter-style distribution)
- `stencil-2d-hybrid.c` (MPI + OpenMP)
- `common.c`, `common.h`
- `Makefile`
- `compare_outputs.py`
- `run_experiments.sh`

## File Format

Matrix file format:

```text
rows cols
v11 v12 v13 ...
v21 v22 v23 ...
...
```

## Build

```bash
make
```

## Generate input

```bash
./make-2d 5 5 input.txt
./print-2d input.txt
```

## Run commands

### Serial
```bash
./stencil-2d -t 3 -i input.txt -o serial_out.txt -p 1 -v 2
```

### Pthreads
```bash
./stencil-2d-pth -t 3 -i input.txt -o pth_out.txt -p 4 -v 2
```

### OpenMP
```bash
./stencil-2d-omp -t 3 -i input.txt -o omp_out.txt -p 4 -v 2
```

### MPI
```bash
mpirun -np 4 ./stencil-2d-mpi -t 3 -i input.txt -o mpi_out.txt -p 4 -v 1
```

### Hybrid
```bash
OMP_NUM_THREADS=2 mpirun -np 4 ./stencil-2d-hybrid -t 3 -i input.txt -o hybrid_out.txt -p 2 -v 1
```

For the hybrid code in this package:
- `mpirun -np X` controls the number of MPI processes.
- `-p` controls the number of OpenMP threads per MPI rank.
- The reported effective `p` is `MPI ranks * OMP threads`.

## Measurements included

Each stencil program prints:

- `T_overall`
- `T_computation`
- `T_other = T_overall - T_computation`
- `n`
- `p`

## Correctness checking

Run serial first, then compare:

```bash
./stencil-2d -t 3 -i input.txt -o serial_out.txt -p 1
./stencil-2d-pth -t 3 -i input.txt -o pth_out.txt -p 4
python compare_outputs.py serial_out.txt pth_out.txt
```

Do the same for OMP, MPI, and Hybrid.

## Experiment plan for the report

Required sizes:
- `n = 5000, 10000, 20000, 40000`

Required thread/process counts:
- `p = 1, 2, 4, 8, 16`

### How to pick `t`

1. Start with the serial version on the 40k matrix and `p=1`.
2. Try a small `t`, for example 20, 50, 100.
3. Increase or decrease until the overall time is about 4 minutes on Expanse.
4. Keep that exact same `t` for every other experiment.

Example calibration loop:

```bash
./make-2d 40000 40000 in_40k.txt

./stencil-2d -t 20  -i in_40k.txt -o out.txt -p 1
./stencil-2d -t 50  -i in_40k.txt -o out.txt -p 1
./stencil-2d -t 100 -i in_40k.txt -o out.txt -p 1
```

Once you find the `t` that gives about 4 minutes overall, run all tests using that same `t`.

## Important note

I made this package to match the assignment structure closely and give you a strong starting point. For the MPI assignment line that explicitly says to use `_Gather()` and `_Scatter()`, many instructors mean the family of collective distribution/gather operations. This implementation uses scatter/gather style row distribution with MPI collectives and `MPI_Sendrecv()` for ghost exchange. If your instructor strictly wants `MPI_Gather()` and `MPI_Scatter()` only, you may need uniform row block sizes or padding.


## Portability note

The Pthreads version in this fixed package uses a custom barrier built from `pthread_mutex_t` and `pthread_cond_t`, so it should compile on systems that do not provide `pthread_barrier_t`.


## Results organization

The experiment script now saves each run in its own directory:

```text
results/
  inputs/
    input_5000.txt
  mpi/
    n5000_p1_t100/
      output.txt
      log.txt
    n5000_p2_t100/
      output.txt
      log.txt
```

That makes it much easier to compare logs and keep output files separated.
