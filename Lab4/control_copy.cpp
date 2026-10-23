// control_copy.cpp — контрольный опыт: скорость копирования (memcpy) int-массива в зависимости от размера.
// Нужен, чтобы проверить объяснение «сверхквадратичного» роста времени у стратегии +100:
// копирование дешевеет, пока исходный и новый буфер помещаются в кэш.
//   g++ -std=c++17 -O2 control_copy.cpp -o control_copy && ./control_copy
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <vector>

int main() {
    for (std::size_t kb : {256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536}) {
        std::size_t n = kb * 1024 / sizeof(int);
        std::vector<int> a(n, 1), b(n, 2);  // оба буфера заранее затронуты: page faults не входят в замер
        std::size_t reps = std::max<std::size_t>(4, static_cast<std::size_t>(2e9 / (n * sizeof(int))));
        double best = 1e9;
        for (int t = 0; t < 5; ++t) {
            auto t0 = std::chrono::steady_clock::now();
            for (std::size_t r = 0; r < reps; ++r) {
                std::memcpy(b.data(), a.data(), n * sizeof(int));
                asm volatile("" : : "r"(b.data()) : "memory");
            }
            double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count() / reps;
            best = std::min(best, s);
        }
        std::printf("буфер %6zu КБ: %.3f нс на элемент int, %.1f ГБ/с\n", kb, best / n * 1e9, n * sizeof(int) / best / 1e9);
    }
    return 0;
}
