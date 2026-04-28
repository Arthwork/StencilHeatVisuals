#include "common.h"
#include <omp.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char *argv[]) {
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

    if (!infile || !outfile || p <= 0 || t < 0) {
        fprintf(stderr, "Usage: %s -t <num iters> -i <in> -o <out> -p <num threads> [-v <0|1|2>]\n", argv[0]);
        return 1;
    }

    double start_overall = get_time();

    Matrix a = {0}, b = {0};
    if (!read_matrix_file(infile, &a)) return 1;
    b = allocate_matrix(a.rows, a.cols);
    init_boundary_preserving_copy(&b, &a);
    omp_set_num_threads(p);

    if (v >= 1) {
        printf("Input: %s\nOutput: %s\nRows: %d\nCols: %d\nIterations: %d\nThreads: %d\n",
               infile, outfile, a.rows, a.cols, t, p);
    }
    if (v >= 2) print_matrix(&a, "Iteration 0");

    double start_compute = get_time();

    for (int iter = 1; iter <= t; iter++) {
        #pragma omp parallel for schedule(static)
        for (int i = 1; i < a.rows - 1; i++) {
            for (int j = 1; j < a.cols - 1; j++) {
                b.data[IDX(&b, i, j)] =
                    (a.data[IDX(&a, i - 1, j)] +
                     a.data[IDX(&a, i + 1, j)] +
                     a.data[IDX(&a, i, j - 1)] +
                     a.data[IDX(&a, i, j + 1)]) / 4.0;
            }
        }
        swap_matrix(&a, &b);

        if (v >= 2) {
            char label[64];
            snprintf(label, sizeof(label), "Iteration %d", iter);
            print_matrix(&a, label);
        }
    }

    double end_compute = get_time();

    if (!write_matrix_file(outfile, &a)) {
        free_matrix(&a);
        free_matrix(&b);
        return 1;
    }

    double end_overall = get_time();
    print_performance_summary(a.rows, p, end_overall - start_overall, end_compute - start_compute);

    free_matrix(&a);
    free_matrix(&b);
    return 0;
}
