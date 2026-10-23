// control_std_vs_sub.cpp — контрольный опыт к разделу 2 отчёта: откуда разница между std::vector
// и subvector x2 при одинаковой последовательности ёмкостей.
// Три заполнения одинаковой длины: std::vector, subvector x2 (копирует старый буфер поэлементным циклом)
// и самодельный вектор x2, копирующий через memcpy из glibc (как делает std::vector через memmove).
// Запуск в разных настройках glibc — скрипт run_controls.sh.
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <vector>

#include <sys/resource.h>

#include "subvector.h"

static double now() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static long faults() {
    rusage r{};
    getrusage(RUSAGE_SELF, &r);
    return r.ru_minflt;
}
static volatile unsigned long long sink;

__attribute__((noinline, flatten)) static double fill_std(unsigned n) {
    double t = now();
    std::vector<int> v;
    for (unsigned i = 0; i < n; ++i) v.push_back(static_cast<int>(i));
    double e = now() - t;
    sink = sink + v[n / 2];
    return e;
}

__attribute__((noinline, flatten)) static double fill_sub(unsigned n) {
    double t = now();
    subvector<int> v(Growth::mul(2.0));
    for (unsigned i = 0; i < n; ++i) v.push_back(static_cast<int>(i));
    double e = now() - t;
    sink = sink + v[n / 2];
    return e;
}

__attribute__((noinline)) static double fill_memcpy(unsigned n) {
    double t = now();
    int* d = nullptr;
    unsigned s = 0, c = 0;
    for (unsigned i = 0; i < n; ++i) {
        if (s == c) {
            unsigned nc = c ? 2 * c : 1;
            int* nd = new int[nc];
            if (s) std::memcpy(nd, d, s * sizeof(int));
            delete[] d;
            d = nd;
            c = nc;
        }
        d[s++] = static_cast<int>(i);
    }
    double e = now() - t;
    sink = sink + d[n / 2];
    delete[] d;
    return e;
}

int main() {
    {  // прогрев кучи, как в bench.cpp
        std::vector<char> w(30u << 20, 1);
        sink = sink + static_cast<unsigned char>(w[1]);
    }
    std::printf("%10s | %22s | %22s | %22s\n", "n", "std::vector", "subvector x2", "вектор x2 на memcpy");
    for (unsigned n : {1000000u, 3000000u, 4000000u, 9000000u}) {
        double a = 1e9, b = 1e9, c = 1e9;
        long fa = 0, fb = 0, fc = 0;
        for (int r = 0; r < 9; ++r) {  // чередуем три варианта, берём минимум
            long f = faults();
            double x = fill_std(n);
            if (x < a) { a = x; fa = faults() - f; }
            f = faults();
            x = fill_sub(n);
            if (x < b) { b = x; fb = faults() - f; }
            f = faults();
            x = fill_memcpy(n);
            if (x < c) { c = x; fc = faults() - f; }
        }
        std::printf("%10u | %6.2f нс/эл, %5ld p.f. | %6.2f нс/эл, %5ld p.f. | %6.2f нс/эл, %5ld p.f.\n", n,
                    a / n * 1e9, fa, b / n * 1e9, fb, c / n * 1e9, fc);
    }
    return 0;
}
