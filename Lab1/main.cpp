#include "sortirovki.hpp"
#include <chrono>
#include <fstream>
#include <iostream>
#include <random>
double get_time() {
    return std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()
    ).count() / 1e6;
}
int rand_uns(int min, int max) {
    unsigned seed = 12345;
    static std::default_random_engine e(seed);
    std::uniform_int_distribution<int> d(min, max);
    return d(e);
}
int main() {
    int sizes[] = {10000, 20000, 40000, 80000, 160000};

    std::ofstream f("fast_results.csv");
    f << "n,quick,merge,heap\n";

    for (int k = 0; k < 5; ++k) {
        int n = sizes[k];

        int* a = new int[n];
        int* b = new int[n];
        int* c = new int[n];
        for (int i = 0; i < n; ++i) {
            a[i] = rand_uns(0, n - 1);
            b[i] = a[i];
            c[i] = a[i];
        }

        double start = get_time();
        quick_sort(a, 0, n - 1);
        double quick_time = get_time() - start;

        start = get_time();
        merge_sort(b, 0, n - 1);
        double merge_time = get_time() - start;

        start = get_time();
        heap_sort(c, n);
        double heap_time = get_time() - start;

        f << n << ','
          << quick_time << ','
          << merge_time << ','
          << heap_time << '\n';

        std::cout << "n = " << n
                  << ": quick = " << quick_time
                  << " s, merge = " << merge_time
                  << " s, heap = " << heap_time
                  << " s; середина: "
                  << a[n / 2] << ' '
                  << b[n / 2] << ' '
                  << c[n / 2] << '\n';

        delete[] a;
        delete[] b;
        delete[] c;
    }
}