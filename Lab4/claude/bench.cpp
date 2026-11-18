// Стенд замеров Claude. Запуск: ./bench <часть> <каталог_данных>
//   capacity  — последовательность ёмкостей и конструкторы std::vector
//   strategies— +10, +100, x1.5, x2, std::vector, std::vector+reserve; время и page faults
//   realloc   — одна стратегия, три способа перевыделения (new+цикл, new+memcpy, realloc)
//   factor    — плотная развёртка по множителю k и по n (сглаживает «пилу»)
//   step      — развёртка по слагаемому c при двух n
//   latency   — время каждого отдельного push_back (амортизированная оценка против худшего случая)
//   types     — std::vector<T> с noexcept-move, с бросающим move и только с копированием
// Каждое заполнение — отдельный объект; время только цикла push_back.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <random>
#include <string>
#include <sys/resource.h>
#include <vector>
#include <x86intrin.h>

#include "subvector.h"

using Clock = std::chrono::steady_clock;
static std::string DIR = "data";
static volatile std::uint64_t sink = 0;   // результат заполнения нужен программе — цикл не выбросить

static long minflt() {
    rusage r{};
    getrusage(RUSAGE_SELF, &r);
    return r.ru_minflt;
}

struct Sample { double sec; long faults; };

// ---- одно заполнение ----
static Sample fill_sub(unsigned n, Growth g, Realloc how) {
    long f0, f1;
    Clock::time_point t0, t1;
    {
        subvector<int> v(g, how);
        f0 = minflt();
        t0 = Clock::now();
        for (unsigned i = 0; i < n; ++i) v.push_back(int(i));
        t1 = Clock::now();
        f1 = minflt();
        sink += v.get_size() + unsigned(v[0]) + unsigned(v[n / 2]) + unsigned(v[n - 1]);
    }                                       // деструктор — вне таймера
    return {std::chrono::duration<double>(t1 - t0).count(), f1 - f0};
}

static Sample fill_std(unsigned n, bool reserve) {
    std::vector<int> v;
    if (reserve) v.reserve(n);              // ёмкость выделена до таймера, но страницы ещё не тронуты
    long f0 = minflt();
    auto t0 = Clock::now();
    for (unsigned i = 0; i < n; ++i) v.push_back(int(i));
    auto t1 = Clock::now();
    long f1 = minflt();
    sink += v.size() + unsigned(v[0]) + unsigned(v[n / 2]) + unsigned(v[n - 1]);
    return {std::chrono::duration<double>(t1 - t0).count(), f1 - f0};
}

static Growth add(unsigned c) { return Growth::add(c); }
static Growth mul(double k) { return Growth::mul(k); }

static FILE* open_csv(const std::string& name, const char* header) {
    FILE* f = std::fopen((DIR + "/" + name).c_str(), "w");
    if (!f) { std::perror(name.c_str()); std::exit(1); }
    std::fprintf(f, "%s\n", header);
    return f;
}

// ---------------------------------------------------------------- capacity
static void part_capacity() {
    FILE* f = open_csv("capacity_libstdcxx.csv", "size,capacity");
    std::vector<int> v;
    std::size_t last = v.capacity();
    std::fprintf(f, "0,%zu\n", last);
    for (unsigned i = 0; i < 20000000; ++i) {
        v.push_back(int(i));
        if (v.capacity() != last) { last = v.capacity(); std::fprintf(f, "%zu,%zu\n", v.size(), last); }
    }
    std::fclose(f);

    f = open_csv("std_constructors.csv", "case;size;capacity");
    auto rec = [&](const char* name, const std::vector<int>& x) { std::fprintf(f, "%s;%zu;%zu\n", name, x.size(), x.capacity()); };
    std::vector<int> a; rec("vector<int> a", a);
    std::vector<int> b(10); rec("vector<int> b(10)", b);
    std::vector<int> c(10, 7); rec("vector<int> c(10, 7)", c);
    std::vector<int> d{1, 2, 3}; rec("vector<int> d{1, 2, 3}", d);
    b.push_back(1); rec("b.push_back(1) при size = capacity = 10", b);
    std::vector<int> e(b); rec("vector<int> e(b) — копия", e);
    std::vector<int> m(std::move(e)); rec("vector<int> m(std::move(e)) — перемещение", m);
    rec("e после перемещения", e);
    a.reserve(100); rec("a.reserve(100)", a);
    a.resize(5); rec("a.resize(5)", a);
    a.reserve(10); rec("a.reserve(10) — меньше текущей: ничего", a);
    b.pop_back(); rec("b.pop_back()", b);
    b.clear(); rec("b.clear()", b);
    b.shrink_to_fit(); rec("b.shrink_to_fit()", b);
    std::vector<int> g(5); g.resize(6); rec("vector<int>(5).resize(6)", g);
    std::vector<int> h(5); h.insert(h.end(), 20, 0); rec("vector<int>(5) + insert 20 элементов", h);
    std::fclose(f);
    std::puts("capacity: ok");
}

// ---------------------------------------------------------------- strategies
static void part_strategies() {
    FILE* f = open_csv("strategies.csv", "strategy,n,trial,seconds,minflt");
    struct S { const char* name; std::function<Sample(unsigned)> run; unsigned max_n; int trials; };
    std::vector<S> ss = {
        {"+10", [](unsigned n) { return fill_sub(n, add(10), Realloc::NewLoop); }, 1000000, 3},
        {"+100", [](unsigned n) { return fill_sub(n, add(100), Realloc::NewLoop); }, 3000000, 3},
        {"x1.5", [](unsigned n) { return fill_sub(n, mul(1.5), Realloc::NewLoop); }, 20000000, 7},
        {"x2", [](unsigned n) { return fill_sub(n, mul(2.0), Realloc::NewLoop); }, 20000000, 7},
        {"std::vector", [](unsigned n) { return fill_std(n, false); }, 20000000, 7},
        {"std::vector+reserve", [](unsigned n) { return fill_std(n, true); }, 20000000, 7},
    };
    std::vector<unsigned> ns;
    for (unsigned n = 100000; n <= 1000000; n += 100000) ns.push_back(n);
    for (unsigned n = 1500000; n <= 20000000; n += 500000) ns.push_back(n);
    for (auto& s : ss) s.run(100000);   // прогрев
    std::mt19937 rng(4);
    for (unsigned n : ns) {
        for (int t = 1; t <= 7; ++t) {
            std::vector<int> order(ss.size());
            for (unsigned i = 0; i < ss.size(); ++i) order[i] = int(i);
            std::shuffle(order.begin(), order.end(), rng);
            for (int i : order) {
                if (n > ss[i].max_n || t > ss[i].trials) continue;
                Sample s = ss[i].run(n);
                std::fprintf(f, "%s,%u,%d,%.9f,%ld\n", ss[i].name, n, t, s.sec, s.faults);
            }
        }
        std::fflush(f);
        std::fprintf(stderr, "strategies n=%u\n", n);
    }
    std::fclose(f);
}

// ---------------------------------------------------------------- realloc
static void part_realloc() {
    FILE* f = open_csv("realloc.csv", "strategy,how,n,trial,seconds,minflt");
    FILE* g = open_csv("realloc_moves.csv", "strategy,how,n,growths,address_changes,moved_elements");
    const char* how_names[] = {"new+loop", "new+memcpy", "realloc"};
    struct S { const char* name; Growth g; };
    S ss[] = {{"+10", add(10)}, {"+100", add(100)}, {"x2", mul(2.0)}};
    for (unsigned n = 100000; n <= 500000; n += 100000) {
        for (int t = 1; t <= 3; ++t)
            for (auto& s : ss)
                for (int h = 0; h < 3; ++h) {
                    Sample r = fill_sub(n, s.g, Realloc(h));
                    std::fprintf(f, "%s,%s,%u,%d,%.9f,%ld\n", s.name, how_names[h], n, t, r.sec, r.faults);
                }
        std::fflush(f);
        std::fprintf(stderr, "realloc n=%u\n", n);
    }
    // Сколько раз блок действительно переехал (адрес сменился) — без таймера.
    for (unsigned n : {500000u, 1000000u, 10000000u})
        for (auto& s : ss)
            for (int h = 0; h < 3; ++h) {
                if (n == 10000000u && !s.g.multiply && h != 2) continue;   // +c с копированием на 10 млн — минуты
                subvector<int> v(s.g, Realloc(h));
                unsigned long long grows = 0, moves = 0, moved = 0;
                for (unsigned i = 0; i < n; ++i) {
                    if (v.get_size() == v.get_capacity()) {
                        const int* before = v.get_data();
                        v.push_back(int(i));
                        ++grows;
                        if (before && v.get_data() != before) { ++moves; moved += i; }
                    } else v.push_back(int(i));
                }
                std::fprintf(g, "%s,%s,%u,%llu,%llu,%llu\n", s.name, how_names[h], n, grows, moves, moved);
            }
    std::fclose(f);
    std::fclose(g);
}

// ---------------------------------------------------------------- factor
static void part_factor() {
    FILE* f = open_csv("factor.csv", "factor,n,trial,seconds,minflt,final_capacity,copied");
    std::vector<double> ks;
    for (int i = 11; i <= 40; ++i) ks.push_back(i / 10.0);
    ks.insert(ks.end(), {1.05, 1.618});
    std::vector<unsigned> ns;
    for (int i = 0; i < 37; ++i) ns.push_back(unsigned(1000000 * std::pow(10.0, i / 36.0)));   // 1..10 млн, лог-шаг
    std::mt19937 rng(7);
    for (int t = 1; t <= 3; ++t) {
        std::shuffle(ks.begin(), ks.end(), rng);
        for (double k : ks) {
            for (unsigned n : ns) {
                Sample s = fill_sub(n, mul(k), Realloc::NewLoop);
                // перенесено и итоговая ёмкость — точно, по той же формуле next_capacity
                unsigned cap = 0; unsigned long long copied = 0;
                while (cap < n) { copied += cap; cap = next_capacity(mul(k), cap); }
                std::fprintf(f, "%.3f,%u,%d,%.9f,%ld,%u,%llu\n", k, n, t, s.sec, s.faults, cap, copied);
            }
        }
        std::fflush(f);
        std::fprintf(stderr, "factor trial %d\n", t);
    }
    std::fclose(f);
}

// ---------------------------------------------------------------- step
static void part_step() {
    const char* fn = std::getenv("STEP_CSV") ? std::getenv("STEP_CSV") : "step.csv";
    FILE* f = open_csv(fn, "step,n,trial,seconds,copied,minflt");
    unsigned cs[] = {10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000};
    for (unsigned n : {250000u, 500000u})
        for (int t = 1; t <= 3; ++t)
            for (unsigned c : cs) {
                Sample s = fill_sub(n, add(c), Realloc::NewLoop);
                unsigned long long copied = 0; unsigned cap = 0;
                while (cap < n) { copied += cap; cap += c; }
                std::fprintf(f, "%u,%u,%d,%.9f,%llu,%ld\n", c, n, t, s.sec, copied, s.faults);
            }
    std::fclose(f);
}

// ---------------------------------------------------------------- latency
static void part_latency() {
    FILE* f = open_csv("latency.csv", "strategy,index,cycles");
    FILE* g = open_csv("latency_summary.csv", "strategy,n,total_cycles,p50,p99,p999,max,ops_over_10k");
    const unsigned N = 4000000;
    std::vector<std::uint64_t> cyc(N);
    struct S { const char* name; Growth g; };
    for (S s : {S{"x2", mul(2.0)}, S{"x1.5", mul(1.5)}, S{"+100000", add(100000)}}) {
        subvector<int> v(s.g);
        for (unsigned i = 0; i < N; ++i) {
            std::uint64_t a = __rdtsc();
            v.push_back(int(i));
            std::uint64_t b = __rdtsc();
            cyc[i] = b - a;
        }
        sink += v[N - 1];
        std::uint64_t total = 0, over = 0;
        for (unsigned i = 0; i < N; ++i) {
            total += cyc[i];
            if (cyc[i] > 10000) { ++over; std::fprintf(f, "%s,%u,%llu\n", s.name, i, (unsigned long long)cyc[i]); }
        }
        std::vector<std::uint64_t> sorted(cyc);
        std::sort(sorted.begin(), sorted.end());
        std::fprintf(g, "%s,%u,%llu,%llu,%llu,%llu,%llu,%llu\n", s.name, N, (unsigned long long)total,
                     (unsigned long long)sorted[N / 2], (unsigned long long)sorted[N * 99 / 100],
                     (unsigned long long)sorted[N * 999 / 1000], (unsigned long long)sorted[N - 1],
                     (unsigned long long)over);
    }
    std::fclose(f);
    std::fclose(g);
}

// ---------------------------------------------------------------- types
template <bool NoexceptMove, bool HasMove>
struct Item {
    std::string s;
    explicit Item(int i) : s(std::to_string(i) + std::string(40, 'x')) {}   // длинная строка: в куче
    Item(const Item& o) : s(o.s) {}
    Item& operator=(const Item&) = default;
    Item(Item&& o) noexcept(NoexceptMove) : s(HasMove ? std::move(o.s) : o.s) {}
};

template <class T>
static double fill_items(unsigned n) {
    std::vector<T> v;
    auto t0 = Clock::now();
    for (unsigned i = 0; i < n; ++i) v.emplace_back(int(i));
    auto t1 = Clock::now();
    sink += v.back().s.size();
    return std::chrono::duration<double>(t1 - t0).count();
}

template <class T>
static double fill_items_reserved(unsigned n) {
    std::vector<T> v;
    v.reserve(n);
    auto t0 = Clock::now();
    for (unsigned i = 0; i < n; ++i) v.emplace_back(int(i));
    auto t1 = Clock::now();
    sink += v.back().s.size();
    return std::chrono::duration<double>(t1 - t0).count();
}

static void part_types() {
    FILE* f = open_csv("types.csv", "type,n,trial,seconds");
    for (unsigned n : {250000u, 500000u, 1000000u, 2000000u})
        for (int t = 1; t <= 5; ++t) {
            std::fprintf(f, "move noexcept,%u,%d,%.9f\n", n, t, fill_items<Item<true, true>>(n));
            std::fprintf(f, "move без noexcept,%u,%d,%.9f\n", n, t, fill_items<Item<false, true>>(n));
            std::fprintf(f, "только копия,%u,%d,%.9f\n", n, t, fill_items<Item<true, false>>(n));
            std::fprintf(f, "reserve(n),%u,%d,%.9f\n", n, t, fill_items_reserved<Item<true, true>>(n));
        }
    std::fclose(f);
}

int main(int argc, char** argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench part [dir]\n"); return 1; }
    if (argc > 2) DIR = argv[2];
    std::string p = argv[1];
    if (p == "capacity") part_capacity();
    else if (p == "strategies") part_strategies();
    else if (p == "realloc") part_realloc();
    else if (p == "factor") part_factor();
    else if (p == "step") part_step();
    else if (p == "latency") part_latency();
    else if (p == "types") part_types();
    else { std::fprintf(stderr, "unknown part\n"); return 1; }
    return sink == 42 ? 2 : 0;
}
