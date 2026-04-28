#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>

typedef struct {
    int rows;
    int cols;
    double *data;
} Matrix;

double get_time(void);

Matrix allocate_matrix(int rows, int cols);
void free_matrix(Matrix *m);
void copy_matrix(Matrix *dst, const Matrix *src);
void swap_matrix(Matrix *a, Matrix *b);

int read_matrix_file(const char *filename, Matrix *m);
int write_matrix_file(const char *filename, const Matrix *m);
void init_boundary_preserving_copy(Matrix *dst, const Matrix *src);
void print_matrix(const Matrix *m, const char *label);
int matrices_equal_tol(const Matrix *a, const Matrix *b, double tol);
void print_performance_summary(int n, int p, double t_overall, double t_compute);

#define IDX(m, r, c) ((r) * (m)->cols + (c))

#endif
