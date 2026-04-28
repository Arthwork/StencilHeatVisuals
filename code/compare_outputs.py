import sys

def read_matrix(path):
    with open(path, "r", encoding="utf-8") as f:
        rows, cols = map(int, f.readline().split())
        data = []
        for _ in range(rows):
            data.extend(float(x) for x in f.readline().split())
        return rows, cols, data

def main():
    if len(sys.argv) != 3:
        print("Usage: python compare_outputs.py <file1> <file2>")
        sys.exit(1)

    r1, c1, d1 = read_matrix(sys.argv[1])
    r2, c2, d2 = read_matrix(sys.argv[2])

    if (r1, c1) != (r2, c2):
        print("Mismatch: different dimensions")
        sys.exit(2)

    tol = 1e-6
    for idx, (a, b) in enumerate(zip(d1, d2)):
        if abs(a - b) > tol:
            print(f"Mismatch at flat index {idx}: {a} vs {b}")
            sys.exit(3)

    print("MATCH")

if __name__ == "__main__":
    main()
