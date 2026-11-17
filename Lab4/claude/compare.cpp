// Один драйвер для всех реализаций. Собирается отдельно для каждой (макрос IMPL_*), запускается
// отдельным процессом на каждое измерение: ./compare x2|add10 N  ->  "секунды,контрольная_сумма"
// Все реализации стартуют с пустого объекта (ёмкость 0), как в задании.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>

#if defined(IMPL_FABLE)
#include "../subvector.h"
#elif defined(IMPL_CODEX)
#include "../codex/subvector.hpp"
#elif defined(IMPL_STD)
#include <vector>
#else
#include "subvector.h"
#endif

int main(int argc, char** argv) {
    if (argc != 3) return 1;
    const bool add10 = std::strcmp(argv[1], "add10") == 0;
    const unsigned n = unsigned(std::strtoul(argv[2], nullptr, 10));
#if defined(IMPL_FABLE)
    subvector v;
    if (add10) v.set_growth_step(10); else v.set_growth_factor(2.0);
    auto push = [&](int i) { return v.push_back(i); };
    auto at = [&](unsigned i) { return v.get(i); };
#elif defined(IMPL_CODEX)
    subvector v(add10 ? Growth::add(10) : Growth::multiply(2));
    auto push = [&](int i) { return v.push_back(i); };
    auto at = [&](unsigned i) { return v.data()[i]; };
#elif defined(IMPL_STD)
    if (add10) return 3;   // у std::vector нет прибавляющей стратегии
    std::vector<int> v;
    auto push = [&](int i) { v.push_back(i); return true; };
    auto at = [&](unsigned i) { return v[i]; };
#else
    subvector v; init(&v);
#if defined(IMPL_CLAUDE_REALLOC)
    set_realloc(&v, Realloc::CRealloc);
#endif
    if (add10) set_growth_step(&v, 10); else set_growth_factor(&v, 2.0);
    auto push = [&](int i) { return push_back(&v, i); };
    auto at = [&](unsigned i) { return v.mas[i]; };
#endif
    auto t0 = std::chrono::steady_clock::now();
    for (unsigned i = 0; i < n; ++i)
        if (!push(int(i))) return 2;
    auto t1 = std::chrono::steady_clock::now();
    std::uint64_t sum = 0;
    for (unsigned i = 0; i < n; ++i) sum += unsigned(at(i));
    if (sum != std::uint64_t(n) * (n - 1) / 2) return 4;
    std::printf("%.9f,%llu\n", std::chrono::duration<double>(t1 - t0).count(), (unsigned long long)sum);
#if !defined(IMPL_FABLE) && !defined(IMPL_CODEX) && !defined(IMPL_STD)
    destructor(&v);
#endif
    return 0;
}
