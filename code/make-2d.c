#include "common.h"
#include <stdlib.h>

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr, "Usage: %s <rows> <cols> <output_file>\n", argv[0]);
        return 1;
    }

    int rows = atoi(argv[1]);
    int cols = atoi(argv[2]);
    const char *outfile = argv[3];

    if (rows < 2 || cols < 2) {
        fprintf(stderr, "rows and cols must be >= 2\n");
        return 1;
    }

    Matrix m = allocate_matrix(rows, cols);
    if (!m.data) {
        fprintf(stderr, "Allocation failed\n");
        return 1;
    }

    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
            double value = 0.0;
            if (j == 0 || j == cols - 1) {
                value = 1.0;
            } else if (i == 0 || i == rows - 1) {
                value = 0.0;
            } else {
                value = 0.0;
            }
            m.data[IDX(&m, i, j)] = value;
        }
    }

    if (!write_matrix_file(outfile, &m)) {
        free_matrix(&m);
        return 1;
    }

    free_matrix(&m);
    return 0;
}
