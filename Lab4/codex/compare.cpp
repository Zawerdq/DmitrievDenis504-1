// Build once per implementation; run.py supplies the matching headers and sources.
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

#if defined(USE_JOURNAL)
#include "container.h"
#elif defined(USE_FABLE)
#include "../subvector.h"
#else
#include "subvector.hpp"
#endif

int main(int argc, char** argv) try {
    if (argc != 3) throw std::invalid_argument("usage: compare double|add10 N");
    const std::string mode = argv[1];
    const int n = std::stoi(argv[2]);
    if ((mode != "double" && mode != "add10") || n <= 0)
        throw std::invalid_argument("invalid comparison parameters");
    // All three start empty, with room for one integer, allocated before timing.
#if defined(USE_JOURNAL)
    if (mode != "double") throw std::invalid_argument("Journal only doubles");
    Journal v(1);
    auto push = [&](int i) { return v.add(i); };
    auto read = [&](int i) { return v.data_[i]; };
#elif defined(USE_FABLE)
    subvector v;
    if (mode == "add10") v.set_growth_step(10);
    if (!v.resize(1)) throw std::bad_alloc();
    auto push = [&](int i) { return v.push_back(i); };
    auto read = [&](int i) { return v.get(i); };
#else
    subvector v(mode == "double" ? Growth::multiply(2) : Growth::add(10));
    if (!v.resize(1)) throw std::bad_alloc();
    auto push = [&](int i) { return v.push_back(i); };
    auto read = [&](int i) { return v.data()[i]; };
#endif
    const auto start = std::chrono::steady_clock::now();
    for (int i = 0; i < n; ++i)
        if (!push(i)) throw std::bad_alloc();
    const auto end = std::chrono::steady_clock::now();
    std::uint64_t sum = 0;
    for (int i = 0; i < n; ++i) sum += read(i);
    if (sum != std::uint64_t(n) * (n - 1) / 2)
        throw std::runtime_error("invalid sum");
    std::cout << std::setprecision(12) << std::chrono::duration<double>(end-start).count()
              << ',' << sum << '\n';
} catch (const std::exception& e) {
    std::cerr << e.what() << '\n'; return 1;
}
