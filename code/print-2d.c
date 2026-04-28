#include "common.h"

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <matrix_file>\n", argv[0]);
        return 1;
    }

    Matrix m = {0};
    if (!read_matrix_file(argv[1], &m)) {
        return 1;
    }

    printf("Matrix (%d x %d)\n", m.rows, m.cols);
    printf("----------------------------------------\n");
    print_matrix(&m, NULL);
    printf("----------------------------------------\n");

    free_matrix(&m);
    return 0;
}
