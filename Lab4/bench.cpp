// bench.cpp — исследование std::vector и стратегий роста subvector.
//
//   ./bench capacity   <out_dir>   — как меняется capacity std::vector; поведение конструкторов
//   ./bench strategies <out_dir>   — время заполнения 1..10 млн элементов: +10, +100, x1.5, x2, std::vector
//   ./bench factor     <out_dir>   — время заполнения от множителя
//   ./bench step       <out_dir>   — время заполнения от прибавляемой константы
//   ./bench all        <out_dir>
// Опция: --cap S — не запускать замер, если прогноз его длительности больше S секунд (по умолчанию 20).
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

#include "subvector.h"

namespace {

double get_time() {
    return std::chrono::duration_cast<std::chrono::microseconds>(
               std::chrono::steady_clock::now().time_since_epoch()).count() / 1e6;
}

double g_cap_seconds = 20.0;
volatile unsigned long long g_sink = 0;  // используем результат заполнения, чтобы его нельзя было выбросить

struct Run {
    double seconds;
    unsigned long long reallocations, moved, peak_elements, final_capacity;
};

// Заполнение subvector n элементами с данной стратегией.
Run fill_subvector(Growth g, unsigned int n) {
    double t0 = get_time();
    subvector<int> v(g);
    for (unsigned int i = 0; i < n; ++i)
        if (!v.push_back(static_cast<int>(i))) { std::cerr << "out of memory\n"; std::exit(3); }
    double t1 = get_time();
    g_sink = g_sink + static_cast<unsigned long long>(v[n / 2]) + v.get_size();
    return {t1 - t0, v.stats().reallocations, v.stats().moved_elements, v.stats().peak_elements, v.get_capacity()};
}

// То же для std::vector. Перевыделения считаем по изменению capacity.
Run fill_std(unsigned int n, bool reserve) {
    double t0 = get_time();
    std::vector<int> v;
    if (reserve) v.reserve(n);
    for (unsigned int i = 0; i < n; ++i) v.push_back(static_cast<int>(i));
    double t1 = get_time();
    g_sink = g_sink + static_cast<unsigned long long>(v[n / 2]) + v.size();
    // Отдельный (не замеряемый) проход для статистики перевыделений.
    std::vector<int> w;
    if (reserve) w.reserve(n);
    unsigned long long re = reserve ? 1 : 0, moved = 0, peak = reserve ? n : 0;
    std::size_t cap = w.capacity();
    for (unsigned int i = 0; i < n; ++i) {
        std::size_t before = w.size();
        w.push_back(static_cast<int>(i));
        if (w.capacity() != cap) {
            ++re;
            moved += before;
            peak = std::max<unsigned long long>(peak, cap + w.capacity());
            cap = w.capacity();
        }
    }
    return {t1 - t0, re, moved, peak, static_cast<unsigned long long>(v.capacity())};
}

struct Strategy {
    std::string name;
    std::function<Run(unsigned int)> fill;
    bool quadratic;  // для аддитивных стратегий время растёт ~ n^2
};

double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    std::size_t m = v.size() / 2;
    return v.size() % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

// Сколько повторов делать, если прогноз длительности одного замера равен predicted.
int trials_for(double predicted) {
    if (predicted > 5.0) return 1;
    if (predicted > 1.0) return 3;
    return 7;
}

// Измеряет стратегию для набора n; пропускает n, для которых прогноз > cap.
void sweep(std::ofstream& f, const std::string& series, const std::string& param, const Strategy& s,
           const std::vector<unsigned int>& ns) {
    double last_t = 0;
    unsigned int last_n = 0;
    for (unsigned int n : ns) {
        double predicted = 0;
        if (last_n) {
            double r = double(n) / last_n;
            predicted = last_t * (s.quadratic ? r * r : r);
        }
        if (predicted > g_cap_seconds) {
            f << series << ',' << s.name << ',' << param << ',' << n << ",0,,,,,,skipped_predicted_" << predicted
              << "s\n";
            std::cerr << "  " << s.name << " n=" << n << " skipped (predicted " << predicted << " s)\n";
            continue;
        }
        s.fill(std::min(n, 100000u));  // короткий прогрев распределителя памяти и кода
        int T = trials_for(predicted);
        std::vector<double> ts;
        for (int t = 1; t <= T; ++t) {
            Run r = s.fill(n);
            ts.push_back(r.seconds);
            f << series << ',' << s.name << ',' << param << ',' << n << ',' << t << ',' << r.seconds << ','
              << r.reallocations << ',' << r.moved << ',' << r.peak_elements << ',' << r.final_capacity << ",ok\n";
        }
        last_t = median(ts);
        last_n = n;
        std::cerr << "  " << s.name << " n=" << n << " median " << last_t << " s (" << T << " trials)\n";
        f.flush();
    }
}

std::ofstream open_runs(const std::string& path) {
    std::ofstream f(path);
    f << std::setprecision(17);
    f << "series,strategy,param,n,trial,seconds,reallocations,moved_elements,peak_elements,final_capacity,status\n";
    return f;
}

// ---------------------------------------------------------------- 1. capacity у std::vector
void capacity_study(const std::string& dir) {
    {
        std::ofstream f(dir + "/std_capacity.csv");
        f << "size,capacity\n";
        std::vector<int> v;
        f << 0 << ',' << v.capacity() << '\n';
        for (int i = 1; i <= 2000000; ++i) {
            std::size_t c = v.capacity();
            v.push_back(i);
            if (v.capacity() != c || i <= 1000) f << v.size() << ',' << v.capacity() << '\n';
        }
    }
    // Конструкторы и операции.
    std::ofstream f(dir + "/std_constructors.csv");
    f << "case,size,capacity\n";
    auto row = [&](const std::string& name, const std::vector<int>& v) {
        f << '"' << name << "\"," << v.size() << ',' << v.capacity() << '\n';
    };
    std::vector<int> a;                    row("vector<int> a;", a);
    std::vector<int> b(10);                row("vector<int> b(10);", b);
    std::vector<int> c(10, 7);             row("vector<int> c(10, 7);", c);
    std::vector<int> d{1, 2, 3};           row("vector<int> d{1,2,3};", d);
    std::vector<int> e(b.begin(), b.begin() + 5); row("vector<int> e(b.begin(), b.begin()+5);", e);
    std::vector<int> big;
    for (int i = 0; i < 17; ++i) big.push_back(i);
    row("big: 17 push_back", big);
    std::vector<int> cp(big);              row("vector<int> cp(big);  // копия", cp);
    std::vector<int> as;  as = big;        row("as = big;  // присваивание пустому", as);
    std::vector<int> mv(std::move(cp));    row("vector<int> mv(std::move(cp));", mv);
    row("cp после перемещения", cp);
    big.push_back(17);                     row("big: ещё push_back (18 эл.)", big);
    big.pop_back();                        row("big.pop_back()", big);
    big.clear();                           row("big.clear()", big);
    big.shrink_to_fit();                   row("big.shrink_to_fit() после clear", big);
    std::vector<int> r;  r.reserve(100);   row("r.reserve(100)", r);
    r.push_back(1);                        row("r.reserve(100); r.push_back(1)", r);
    r.reserve(10);                         row("r.reserve(10)  // меньше текущей — не уменьшает", r);
    r.resize(150);                         row("r.resize(150)", r);
    r.resize(5);                           row("r.resize(5)", r);
    std::vector<int> s(5);  s.push_back(1); row("vector<int> s(5); s.push_back(1)", s);
    std::vector<int> t(7);  t.push_back(1); row("vector<int> t(7); t.push_back(1)", t);
    std::vector<int> u;  u.insert(u.end(), {1, 2, 3, 4, 5}); row("u.insert(end, 5 эл.) в пустой", u);
    u.insert(u.end(), {6, 7, 8});          row("u.insert(end, ещё 3) -> 8", u);
    u.insert(u.end(), 20, 0);              row("u.insert(end, 20 нулей) -> 28", u);
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "usage: bench <capacity|strategies|factor|step|all> <out_dir> [--cap seconds]\n";
        return 2;
    }
    std::string mode = argv[1], dir = argv[2];
    for (int i = 3; i + 1 < argc; ++i)
        if (std::string(argv[i]) == "--cap") g_cap_seconds = std::stod(argv[++i]);

    auto sub = [](const std::string& name, Growth g) {
        return Strategy{name, [g](unsigned int n) { return fill_subvector(g, n); }, g.kind == Growth::Add};
    };

    if (mode == "capacity" || mode == "all") {
        std::cerr << "capacity study\n";
        capacity_study(dir);
    }

    if (mode == "strategies" || mode == "all") {
        std::cerr << "strategies\n";
        std::ofstream f = open_runs(dir + "/strategies.csv");
        std::vector<unsigned int> ns;
        for (unsigned int n = 100000; n < 1000000; n += 100000) ns.push_back(n);   // мелкая сетка: видна квадратичность +10/+100
        for (unsigned int n = 1000000; n <= 10000000; n += 1000000) ns.push_back(n);
        std::vector<Strategy> ss = {
            Strategy{"std::vector", [](unsigned int n) { return fill_std(n, false); }, false},
            Strategy{"std::vector+reserve", [](unsigned int n) { return fill_std(n, true); }, false},
            sub("x2", Growth::mul(2.0)),
            sub("x1.5", Growth::mul(1.5)),
            sub("+100", Growth::add(100)),
            sub("+10", Growth::add(10)),
        };
        for (auto& s : ss) sweep(f, "strategies", "", s, ns);
    }

    if (mode == "factor" || mode == "all") {
        std::cerr << "factor sweep\n";
        std::ofstream f = open_runs(dir + "/factor.csv");
        // Время одного заполнения сильно зависит от того, где n оказалось относительно ближайшего
        // перевыделения, поэтому для каждого множителя берём несколько n и затем усредняем нс/элемент.
        const std::vector<unsigned int> ns = {2000000, 4000000, 6000000, 8000000, 10000000};
        std::vector<double> fs = {1.02, 1.05, 1.1, 1.2, 1.3, 1.4, 1.5, 1.618, 1.75, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0, 16.0};
        for (double k : fs) {
            char buf[32];
            std::snprintf(buf, sizeof buf, "%g", k);
            sweep(f, "factor", buf, sub("x" + std::string(buf), Growth::mul(k)), ns);
        }
    }

    if (mode == "step" || mode == "all") {
        std::cerr << "step sweep\n";
        std::ofstream f = open_runs(dir + "/step.csv");
        std::vector<unsigned int> steps = {10000000, 3000000, 1000000, 300000, 100000, 30000, 10000,
                                           3000, 1000, 300, 100, 30, 10};
        for (unsigned int n : {1000000u, 10000000u}) {
            // идём от больших шагов к маленьким и прогнозируем время ~ n^2 / step
            double last_t = 0;
            unsigned int last_step = 0;
            for (unsigned int st : steps) {
                double predicted = last_step ? last_t * double(last_step) / st : 0;
                std::string param = std::to_string(st);
                if (predicted > g_cap_seconds) {
                    f << "step_n" << n << ",+" << st << ',' << param << ',' << n << ",0,,,,,,skipped_predicted_"
                      << predicted << "s\n";
                    std::cerr << "  +" << st << " n=" << n << " skipped (predicted " << predicted << " s)\n";
                    continue;
                }
                Strategy s = sub("+" + param, Growth::add(st));
                s.fill(100000);
                int T = trials_for(predicted);
                std::vector<double> ts;
                for (int t = 1; t <= T; ++t) {
                    Run r = s.fill(n);
                    ts.push_back(r.seconds);
                    f << "step_n" << n << ',' << s.name << ',' << param << ',' << n << ',' << t << ',' << r.seconds
                      << ',' << r.reallocations << ',' << r.moved << ',' << r.peak_elements << ','
                      << r.final_capacity << ",ok\n";
                }
                double m = median(ts);
                // прогноз используем только когда время уже определяется копированием
                if (m > 0.05) { last_t = m; last_step = st; }
                std::cerr << "  +" << st << " n=" << n << " median " << m << " s\n";
                f.flush();
            }
        }
    }
    std::cerr << "sink " << g_sink << "\n";
    return 0;
}
