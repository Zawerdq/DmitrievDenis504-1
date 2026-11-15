#include "subvector.hpp"
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
struct Case { std::string name; double factor; unsigned step; };

void append(subvector& v, int n) {
    if (!v.push_back(n)) throw std::bad_alloc();
}
void append(std::vector<int>& v, int n) { v.push_back(n); }

template<class F>
void with_vector(const Case& c, F run) {
    if (c.name == "std") {
        std::vector<int> v;
        run(v);
    } else {
        subvector v(c.step ? Growth::add(c.step) : Growth::multiply(c.factor));
        run(v);
    }
}

std::ofstream csv(const fs::path& path, const char* header) {
    std::ofstream out;
    out.exceptions(std::ios::failbit | std::ios::badbit);
    out.open(path);
    out << header << '\n' << std::setprecision(10);
    return out;
}

template<class V>
void timed(V& v, const Case& c, unsigned repeat, unsigned max_n, std::ostream& out) {
    struct Sample { unsigned n; double seconds; std::size_t capacity; };
    std::vector<Sample> samples;
    samples.reserve(max_n / 1000000);
    unsigned i = 0;
    double elapsed = 0;
    while (i < max_n) {
        unsigned stop = i + 1000000;
        auto start = Clock::now();
        for (; i < stop; ++i) append(v, static_cast<int>(i));
        elapsed += std::chrono::duration<double>(Clock::now() - start).count();
        samples.push_back({i, elapsed, v.capacity()});
    }
    const auto sum = std::accumulate(v.data(), v.data() + max_n, std::uint64_t{0});
    if (sum != std::uint64_t(max_n) * (max_n - 1) / 2)
        throw std::runtime_error("invalid sum");
    for (auto s : samples)
        out << c.name << ',' << c.factor << ',' << c.step << ',' << repeat << ','
            << s.n << ',' << s.seconds << ',' << s.capacity << '\n';
    out.flush();
}

template<class V>
void trace(V& v, const Case& c, unsigned n, std::ostream& out) {
    unsigned grows = 0, moves = 0;
    std::uint64_t prefix = 0;
    for (unsigned i = 0; i < n; ++i) {
        if (v.size() < v.capacity()) {
            append(v, static_cast<int>(i));
            continue;
        }
        auto addr = reinterpret_cast<std::uintptr_t>(v.data());
        append(v, static_cast<int>(i));
        ++grows;
        if (i && reinterpret_cast<std::uintptr_t>(v.data()) != addr) {
            ++moves;
            prefix += i;
        }
    }
    out << c.name << ',' << n << ',' << grows << ',' << moves << ',' << prefix
        << ',' << v.capacity() << '\n';
}

int main(int argc, char** argv) try {
    if (argc != 2) throw std::invalid_argument("usage: benchmark OUTPUT_DIRECTORY");
    fs::path dir(argv[1]);
    fs::create_directories(dir);
    auto capacity = csv(dir / "std_capacity.csv", "size,capacity");
    std::vector<int> standard;
    capacity << "0," << standard.capacity() << '\n';
    for (int i = 1; i <= 256; ++i) {
        standard.push_back(i);
        capacity << i << ',' << standard.capacity() << '\n';
    }
    auto constructors = csv(dir / "std_constructors.csv", "constructor,size,capacity,values");
    auto record = [&](const char* name, const std::vector<int>& v) {
        constructors << name << ',' << v.size() << ',' << v.capacity() << ',';
        for (std::size_t i = 0; i < v.size(); ++i) {
            if (i) constructors << ' ';
            constructors << v[i];
        }
        constructors << '\n';
    };
    std::vector<int> empty, zeros(4), fill(4, 7), list{4, 7}, copy(list);
    std::vector<int> range(fill.begin() + 1, fill.end());
    record("default", empty); record("count", zeros); record("fill", fill);
    record("initializer_list", list); record("copy", copy); record("range", range);
    std::vector<int> moved(std::move(copy));
    record("move", moved);

    std::vector<Case> cases{{"std",0,0}, {"add_10",0,10}, {"add_100",0,100},
                            {"mul_1.5",1.5,0}, {"mul_2",2,0}};
    for (unsigned s : {1u, 5u, 25u, 50u, 250u, 1000u, 10000u})
        cases.push_back({"add_" + std::to_string(s), 0, s});
    for (double f : {1.05, 1.1, 1.25, 1.75, 2.5, 3.0, 4.0})
        cases.push_back({"mul_" + std::to_string(f), f, 0});
    auto times = csv(dir / "times.csv", "strategy,factor,step,repeat,n,seconds,capacity");
    auto counts = csv(dir / "growth.csv", "strategy,n,growths,address_changes,prefix_elements,capacity");
    std::mt19937 rng(20261115);
    std::vector<unsigned> order(cases.size());
    std::iota(order.begin(), order.end(), 0);
    for (unsigned repeat = 1; repeat <= 5; ++repeat) {
        std::shuffle(order.begin(), order.end(), rng);
        for (auto k : order) {
            unsigned n = k < 5 ? 10000000 : 1000000;
            with_vector(cases[k], [&](auto& v) { timed(v, cases[k], repeat, n, times); });
        }
        std::cerr << "Round " << repeat << " complete\n";
    }
    for (auto& c : cases)
        with_vector(c, [&](auto& v) { trace(v, c, 1000000, counts); });
} catch (const std::exception& e) {
    std::cerr << e.what() << '\n'; return 1;
}
