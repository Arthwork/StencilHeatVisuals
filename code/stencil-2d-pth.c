#include "common.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t cond;
    int count;
    int trip_count;
    int generation;
} simple_barrier_t;

typedef struct {
    int tid;
    int num_threads;
    int iterations;
    int verbose;
} ThreadArg;

static Matrix current_m;
static Matrix next_m;
static simple_barrier_t barrier;

static void barrier_init(simple_barrier_t *b, int trip_count) {
    pthread_mutex_init(&b->mutex, NULL);
    pthread_cond_init(&b->cond, NULL);
    b->count = 0;
    b->trip_count = trip_count;
    b->generation = 0;
}

static void barrier_wait(simple_barrier_t *b) {
    pthread_mutex_lock(&b->mutex);
    int gen = b->generation;

    b->count++;
    if (b->count == b->trip_count) {
        b->generation++;
        b->count = 0;
        pthread_cond_broadcast(&b->cond);
        pthread_mutex_unlock(&b->mutex);
        return;
    }

    while (gen == b->generation) {
        pthread_cond_wait(&b->cond, &b->mutex);
    }
    pthread_mutex_unlock(&b->mutex);
}

static void barrier_destroy(simple_barrier_t *b) {
    pthread_mutex_destroy(&b->mutex);
    pthread_cond_destroy(&b->cond);
}

static void compute_range(int tid, int num_threads) {
    int inner_rows = current_m.rows - 2;
    int base = inner_rows / num_threads;
    int rem = inner_rows % num_threads;

    int my_rows = base + (tid < rem ? 1 : 0);
    int start_inner = 1 + tid * base + (tid < rem ? tid : rem);
    int end_inner = start_inner + my_rows - 1;

    for (int i = start_inner; i <= end_inner; i++) {
        for (int j = 1; j < current_m.cols - 1; j++) {
            next_m.data[IDX(&next_m, i, j)] =
                (current_m.data[IDX(&current_m, i - 1, j)] +
                 current_m.data[IDX(&current_m, i + 1, j)] +
                 current_m.data[IDX(&current_m, i, j - 1)] +
                 current_m.data[IDX(&current_m, i, j + 1)]) / 4.0;
        }
    }
}

static void *worker(void *arg) {
    ThreadArg *a = (ThreadArg *) arg;
    for (int iter = 1; iter <= a->iterations; iter++) {
        compute_range(a->tid, a->num_threads);
        barrier_wait(&barrier);

        if (a->tid == 0) {
            swap_matrix(&current_m, &next_m);
            if (a->verbose >= 2) {
                char label[64];
                snprintf(label, sizeof(label), "Iteration %d", iter);
                print_matrix(&current_m, label);
            }
        }

        barrier_wait(&barrier);
    }
    return NULL;
}

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

    if (!read_matrix_file(infile, &current_m)) return 1;
    next_m = allocate_matrix(current_m.rows, current_m.cols);
    init_boundary_preserving_copy(&next_m, &current_m);

    if (v >= 1) {
        printf("Input: %s\nOutput: %s\nRows: %d\nCols: %d\nIterations: %d\nThreads: %d\n",
               infile, outfile, current_m.rows, current_m.cols, t, p);
    }
    if (v >= 2) print_matrix(&current_m, "Iteration 0");

    pthread_t *threads = (pthread_t *) malloc((size_t) p * sizeof(pthread_t));
    ThreadArg *args = (ThreadArg *) malloc((size_t) p * sizeof(ThreadArg));
    if (!threads || !args) {
        fprintf(stderr, "Allocation failed for thread structures\n");
        free(threads);
        free(args);
        free_matrix(&current_m);
        free_matrix(&next_m);
        return 1;
    }

    barrier_init(&barrier, p);

    double start_compute = get_time();

    for (int tid = 0; tid < p; tid++) {
        args[tid].tid = tid;
        args[tid].num_threads = p;
        args[tid].iterations = t;
        args[tid].verbose = v;
        if (pthread_create(&threads[tid], NULL, worker, &args[tid]) != 0) {
            fprintf(stderr, "Failed to create thread %d\n", tid);
            return 1;
        }
    }

    for (int tid = 0; tid < p; tid++) {
        pthread_join(threads[tid], NULL);
    }

    double end_compute = get_time();

    if (!write_matrix_file(outfile, &current_m)) {
        free(threads);
        free(args);
        free_matrix(&current_m);
        free_matrix(&next_m);
        return 1;
    }

    double end_overall = get_time();
    print_performance_summary(current_m.rows, p, end_overall - start_overall, end_compute - start_compute);

    barrier_destroy(&barrier);
    free(threads);
    free(args);
    free_matrix(&current_m);
    free_matrix(&next_m);
    return 0;
}
