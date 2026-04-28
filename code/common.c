#include "common.h"
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <math.h>

double get_time(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (double) tv.tv_sec + (double) tv.tv_usec / 1000000.0;
}

Matrix allocate_matrix(int rows, int cols) {
    Matrix m;
    m.rows = rows;
    m.cols = cols;
    m.data = (double *) calloc((size_t) rows * (size_t) cols, sizeof(double));
    return m;
}

void free_matrix(Matrix *m) {
    if (m && m->data) {
        free(m->data);
        m->data = NULL;
    }
    if (m) {
        m->rows = 0;
        m->cols = 0;
    }
}

void copy_matrix(Matrix *dst, const Matrix *src) {
    if (!dst || !src || !dst->data || !src->data) return;
    memcpy(dst->data, src->data, (size_t) src->rows * (size_t) src->cols * sizeof(double));
}

void swap_matrix(Matrix *a, Matrix *b) {
    Matrix tmp = *a;
    *a = *b;
    *b = tmp;
}

int read_matrix_file(const char *filename, Matrix *m) {
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        perror("fopen input");
        return 0;
    }

    int rows = 0, cols = 0;
    if (fscanf(fp, "%d %d", &rows, &cols) != 2 || rows <= 0 || cols <= 0) {
        fprintf(stderr, "Invalid matrix header in %s\n", filename);
        fclose(fp);
        return 0;
    }

    *m = allocate_matrix(rows, cols);
    if (!m->data) {
        fprintf(stderr, "Failed to allocate matrix\n");
        fclose(fp);
        return 0;
    }

    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
            if (fscanf(fp, "%lf", &m->data[IDX(m, i, j)]) != 1) {
                fprintf(stderr, "Invalid matrix data in %s at (%d,%d)\n", filename, i, j);
                fclose(fp);
                free_matrix(m);
                return 0;
            }
        }
    }

    fclose(fp);
    return 1;
}

int write_matrix_file(const char *filename, const Matrix *m) {
    FILE *fp = fopen(filename, "w");
    if (!fp) {
        perror("fopen output");
        return 0;
    }

    fprintf(fp, "%d %d\n", m->rows, m->cols);
    for (int i = 0; i < m->rows; i++) {
        for (int j = 0; j < m->cols; j++) {
            fprintf(fp, "%.6f", m->data[IDX(m, i, j)]);
            if (j + 1 < m->cols) fprintf(fp, " ");
        }
        fprintf(fp, "\n");
    }

    fclose(fp);
    return 1;
}

void init_boundary_preserving_copy(Matrix *dst, const Matrix *src) {
    copy_matrix(dst, src);
}

void print_matrix(const Matrix *m, const char *label) {
    if (label && *label) {
        printf("%s\n", label);
    }
    for (int i = 0; i < m->rows; i++) {
        for (int j = 0; j < m->cols; j++) {
            printf("%7.2f ", m->data[IDX(m, i, j)]);
        }
        printf("\n");
    }
}

int matrices_equal_tol(const Matrix *a, const Matrix *b, double tol) {
    if (!a || !b || a->rows != b->rows || a->cols != b->cols) return 0;
    for (int i = 0; i < a->rows * a->cols; i++) {
        if (fabs(a->data[i] - b->data[i]) > tol) return 0;
    }
    return 1;
}

void print_performance_summary(int n, int p, double t_overall, double t_compute) {
    double t_other = t_overall - t_compute;
    printf("Performance Summary\n");
    printf("-------------------\n");
    printf("n                 = %d\n", n);
    printf("p                 = %d\n", p);
    printf("T_overall         = %.6f sec\n", t_overall);
    printf("T_computation     = %.6f sec\n", t_compute);
    printf("T_other           = %.6f sec\n", t_other);
}
