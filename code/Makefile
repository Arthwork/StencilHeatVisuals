CC = gcc
MPICC = mpicc
CFLAGS = -Wall -Wextra -O2 -std=c11
OMPFLAGS = -fopenmp
PTHFLAGS = -pthread

COMMON_OBJ = common.o

all: make-2d print-2d stencil-2d stencil-2d-pth stencil-2d-omp stencil-2d-mpi stencil-2d-hybrid

common.o: common.c common.h
	$(CC) $(CFLAGS) -c common.c

make-2d: make-2d.c $(COMMON_OBJ)
	$(CC) $(CFLAGS) -o $@ make-2d.c $(COMMON_OBJ)

print-2d: print-2d.c $(COMMON_OBJ)
	$(CC) $(CFLAGS) -o $@ print-2d.c $(COMMON_OBJ)

stencil-2d: stencil-2d.c $(COMMON_OBJ)
	$(CC) $(CFLAGS) -o $@ stencil-2d.c $(COMMON_OBJ)

stencil-2d-pth: stencil-2d-pth.c $(COMMON_OBJ)
	$(CC) $(CFLAGS) -o $@ stencil-2d-pth.c $(COMMON_OBJ) $(PTHFLAGS)

stencil-2d-omp: stencil-2d-omp.c $(COMMON_OBJ)
	$(CC) $(CFLAGS) $(OMPFLAGS) -o $@ stencil-2d-omp.c $(COMMON_OBJ)

stencil-2d-mpi: stencil-2d-mpi.c common.c common.h
	$(MPICC) $(CFLAGS) -o $@ stencil-2d-mpi.c common.c

stencil-2d-hybrid: stencil-2d-hybrid.c common.c common.h
	$(MPICC) $(CFLAGS) $(OMPFLAGS) -o $@ stencil-2d-hybrid.c common.c

clean:
	rm -f *.o make-2d print-2d stencil-2d stencil-2d-pth stencil-2d-omp stencil-2d-mpi stencil-2d-hybrid *.txt

.PHONY: all clean
