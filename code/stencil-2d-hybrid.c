#include "common.h"
#include <mpi.h>
#include <omp.h>
#include <stdlib.h>
#include <string.h>

static void build_row_distribution(int global_rows, int cols, int size,
                                   int *counts_scatter, int *displs_scatter,
                                   int *counts_gather, int *displs_gather,
                                   int *inner_rows_per_rank) {
    int inner_rows = global_rows - 2;
    int base = inner_rows / size;
    int rem = inner_rows % size;

    int scatter_offset_rows = 1;
    int gather_offset_rows = 0;

    for (int r = 0; r < size; r++) {
        inner_rows_per_rank[r] = base + (r < rem ? 1 : 0);

        counts_scatter[r] = inner_rows_per_rank[r] * cols;
        displs_scatter[r] = scatter_offset_rows * cols;
        scatter_offset_rows += inner_rows_per_rank[r];

        counts_gather[r] = inner_rows_per_rank[r] * cols;
        displs_gather[r] = gather_offset_rows * cols;
        gather_offset_rows += inner_rows_per_rank[r];
    }
}

int main(int argc, char *argv[]) {
    MPI_Init(&argc, &argv);

    int rank = 0, size = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    int t = 1;
    int p = 1;
    int v = 0;
    char *infile = NULL;
    char *outfile = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-t") == 0 && i + 1 < argc) t = atoi(argv[++i]);
        else if (strcmp(argv[i], "-i") == 0 && i + 1 < argc) infile = argv[++i];
        else if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) outfile = argv[++i];
        else if (strcmp(argv[i], "-p") == 0 && i + 1 < argc) p = atoi(argv[++i]);
        else if (strcmp(argv[i], "-v") == 0 && i + 1 < argc) v = atoi(argv[++i]);
    }

    if (!infile || !outfile || t < 0 || p <= 0) {
        if (rank == 0) {
            fprintf(stderr, "Usage: %s -t <num iters> -i <in> -o <out> -p <omp threads per MPI rank> [-v <0|1|2>]\n", argv[0]);
        }
        MPI_Finalize();
        return 1;
    }

    omp_set_num_threads(p);

    double start_overall = MPI_Wtime();

    Matrix global = {0};
    int rows = 0, cols = 0;

    if (rank == 0) {
        if (!read_matrix_file(infile, &global)) MPI_Abort(MPI_COMM_WORLD, 1);
        rows = global.rows;
        cols = global.cols;
    }

    MPI_Bcast(&rows, 1, MPI_INT, 0, MPI_COMM_WORLD);
    MPI_Bcast(&cols, 1, MPI_INT, 0, MPI_COMM_WORLD);

    int *counts_scatter = (int *) malloc((size_t) size * sizeof(int));
    int *displs_scatter = (int *) malloc((size_t) size * sizeof(int));
    int *counts_gather  = (int *) malloc((size_t) size * sizeof(int));
    int *displs_gather  = (int *) malloc((size_t) size * sizeof(int));
    int *inner_rows_per_rank = (int *) malloc((size_t) size * sizeof(int));

    build_row_distribution(rows, cols, size,
                           counts_scatter, displs_scatter,
                           counts_gather, displs_gather,
                           inner_rows_per_rank);

    int local_inner_rows = inner_rows_per_rank[rank];
    int local_rows_with_ghosts = local_inner_rows + 2;

    double *local_old = (double *) calloc((size_t) local_rows_with_ghosts * (size_t) cols, sizeof(double));
    double *local_new = (double *) calloc((size_t) local_rows_with_ghosts * (size_t) cols, sizeof(double));
    double *top_boundary = (double *) calloc((size_t) cols, sizeof(double));
    double *bottom_boundary = (double *) calloc((size_t) cols, sizeof(double));

    if (!counts_scatter || !displs_scatter || !counts_gather || !displs_gather || !inner_rows_per_rank ||
        !local_old || !local_new || !top_boundary || !bottom_boundary) {
        fprintf(stderr, "Rank %d: allocation failure\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 20);
    }

    if (rank == 0) {
        for (int j = 0; j < cols; j++) {
            top_boundary[j] = global.data[IDX(&global, 0, j)];
            bottom_boundary[j] = global.data[IDX(&global, rows - 1, j)];
        }
    }

    MPI_Bcast(top_boundary, cols, MPI_DOUBLE, 0, MPI_COMM_WORLD);
    MPI_Bcast(bottom_boundary, cols, MPI_DOUBLE, 0, MPI_COMM_WORLD);

    MPI_Scatterv(rank == 0 ? global.data : NULL,
                 counts_scatter, displs_scatter, MPI_DOUBLE,
                 &local_old[cols], counts_scatter[rank], MPI_DOUBLE,
                 0, MPI_COMM_WORLD);

    memcpy(local_new, local_old, (size_t) local_rows_with_ghosts * (size_t) cols * sizeof(double));

    if (rank == 0 && v >= 1) {
        printf("Input: %s\nOutput: %s\nRows: %d\nCols: %d\nIterations: %d\nMPI Processes: %d\nOMP Threads/Rank: %d\n",
               infile, outfile, rows, cols, t, size, p);
    }

    double start_compute = MPI_Wtime();

    for (int iter = 1; iter <= t; iter++) {
        int up = (rank == 0) ? MPI_PROC_NULL : rank - 1;
        int down = (rank == size - 1) ? MPI_PROC_NULL : rank + 1;

        MPI_Sendrecv(&local_old[cols], cols, MPI_DOUBLE, up, 300,
                     &local_old[0], cols, MPI_DOUBLE, up, 400,
                     MPI_COMM_WORLD, MPI_STATUS_IGNORE);

        MPI_Sendrecv(&local_old[local_inner_rows * cols], cols, MPI_DOUBLE, down, 400,
                     &local_old[(local_inner_rows + 1) * cols], cols, MPI_DOUBLE, down, 300,
                     MPI_COMM_WORLD, MPI_STATUS_IGNORE);

        if (rank == 0) {
            memcpy(&local_old[0], top_boundary, (size_t) cols * sizeof(double));
        }
        if (rank == size - 1) {
            memcpy(&local_old[(local_inner_rows + 1) * cols], bottom_boundary, (size_t) cols * sizeof(double));
        }

        #pragma omp parallel for schedule(static)
        for (int li = 1; li <= local_inner_rows; li++) {
            for (int j = 1; j < cols - 1; j++) {
                local_new[li * cols + j] =
                    (local_old[(li - 1) * cols + j] +
                     local_old[(li + 1) * cols + j] +
                     local_old[li * cols + (j - 1)] +
                     local_old[li * cols + (j + 1)]) / 4.0;
            }
            local_new[li * cols + 0] = 1.0;
            local_new[li * cols + (cols - 1)] = 1.0;
        }

        double *tmp = local_old;
        local_old = local_new;
        local_new = tmp;
    }

    double end_compute = MPI_Wtime();

    double *gathered_inner = NULL;
    if (rank == 0) {
        gathered_inner = (double *) calloc((size_t) (rows - 2) * (size_t) cols, sizeof(double));
        if (!gathered_inner) {
            fprintf(stderr, "Rank 0: allocation failure for gathered buffer\n");
            MPI_Abort(MPI_COMM_WORLD, 21);
        }
    }

    MPI_Gatherv(&local_old[cols], counts_gather[rank], MPI_DOUBLE,
                gathered_inner, counts_gather, displs_gather, MPI_DOUBLE,
                0, MPI_COMM_WORLD);

    if (rank == 0) {
        Matrix out = allocate_matrix(rows, cols);
        if (!out.data) {
            fprintf(stderr, "Rank 0: allocation failure for output matrix\n");
            MPI_Abort(MPI_COMM_WORLD, 22);
        }

        memcpy(&out.data[0], top_boundary, (size_t) cols * sizeof(double));
        if (rows > 2) {
            memcpy(&out.data[cols], gathered_inner, (size_t) (rows - 2) * (size_t) cols * sizeof(double));
        }
        memcpy(&out.data[(rows - 1) * cols], bottom_boundary, (size_t) cols * sizeof(double));

        if (!write_matrix_file(outfile, &out)) MPI_Abort(MPI_COMM_WORLD, 2);

        double end_overall = MPI_Wtime();
        print_performance_summary(rows, size * p, end_overall - start_overall, end_compute - start_compute);

        if (v >= 2) {
            print_matrix(&out, "Final Matrix");
        }

        free_matrix(&out);
    }

    free(counts_scatter);
    free(displs_scatter);
    free(counts_gather);
    free(displs_gather);
    free(inner_rows_per_rank);
    free(local_old);
    free(local_new);
    free(top_boundary);
    free(bottom_boundary);
    free(gathered_inner);
    if (rank == 0) free_matrix(&global);

    MPI_Finalize();
    return 0;
}
