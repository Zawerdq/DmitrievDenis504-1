// control_order.cpp — контрольный опыт к разделу 2 отчёта.
// Одинаковые заполнения std::vector и subvector x2 (n = 100 000) в одном процессе,
// в разном порядке и с прогревом кучи / без него. Печатает время и число page faults.
//
//   g++ -std=c++17 -O2 control_order.cpp -o control_order
//   ./control_order            — без прогрева кучи
//   ./control_order warm       — сначала выделить и освободить 30 МБ
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

int main(int argc, char** argv) {
    if (argc > 1 && std::strcmp(argv[1], "warm") == 0) {
        std::vector<char> w(30u << 20, 1);
        sink = sink + static_cast<unsigned char>(w[1]);
    }
    const unsigned n = 100000;
    std::printf("%s\n", argc > 1 ? "с прогревом кучи" : "без прогрева кучи");
    for (int round = 0; round < 2; ++round) {
        for (int k = 0; k < 2; ++k) {
            bool std_first = (round == 0);
            const char* name = (k == 0) == std_first ? "std::vector" : "subvector x2";
            for (int r = 0; r < 3; ++r) {
                long f0 = faults();
                double t = ((k == 0) == std_first) ? fill_std(n) : fill_sub(n);
                long f1 = faults();
                std::printf("  %-13s %6.2f нс/элемент, page faults: %ld\n", name, t / n * 1e9, f1 - f0);
            }
        }
    }
    return 0;
}
