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
#include <random>
#include <string>
#include <vector>

#include <sys/resource.h>

#include "subvector.h"

namespace {

double get_time() {
    return std::chrono::duration_cast<std::chrono::microseconds>(
               std::chrono::steady_clock::now().time_since_epoch()).count() / 1e6;
}

// Число «мягких» page fault'ов процесса (первое касание страницы, выданной ядром).
// Читается до и после замеряемого участка, но вне интервала get_time().
long minor_faults() {
    rusage r{};
    getrusage(RUSAGE_SELF, &r);
    return r.ru_minflt;
}

double g_cap_seconds = 20.0;
volatile unsigned long long g_sink = 0;  // используем результат заполнения, чтобы его нельзя было выбросить

struct Run {
    double seconds;
    unsigned long long reallocations, moved, peak_elements, final_capacity;
    long page_faults = 0;
};

// Заполнение subvector n элементами с данной стратегией.
// flatten: всё, что вызывается внутри (push_back, resize), встраивается — так же, как в fill_std ниже.
// Без этого g++ встраивал push_back у subvector, но НЕ у std::vector (там оставался вызов emplace_back на
// каждый элемент), и сравнение показывало разницу кодогенерации, а не стратегий роста.
__attribute__((flatten)) Run fill_subvector(Growth g, unsigned int n) {
    long f0 = minor_faults();
    double t0 = get_time();
    subvector<int> v(g);
    for (unsigned int i = 0; i < n; ++i)
        if (!v.push_back(static_cast<int>(i))) { std::cerr << "out of memory\n"; std::exit(3); }
    double t1 = get_time();
    long f1 = minor_faults();
    g_sink = g_sink + static_cast<unsigned long long>(v[n / 2]) + v.get_size();
    return {t1 - t0, v.stats().reallocations, v.stats().moved_elements, v.stats().peak_elements, v.get_capacity(),
            f1 - f0};
}

// Замеряемая часть для std::vector (flatten — см. комментарий к fill_subvector).
__attribute__((flatten)) double time_std(unsigned int n, bool reserve, std::size_t& cap, long& faults) {
    long f0 = minor_faults();
    double t0 = get_time();
    std::vector<int> v;
    if (reserve) v.reserve(n);
    for (unsigned int i = 0; i < n; ++i) v.push_back(static_cast<int>(i));
    double t1 = get_time();
    faults = minor_faults() - f0;
    g_sink = g_sink + static_cast<unsigned long long>(v[n / 2]) + v.size();
    cap = v.capacity();
    return t1 - t0;
}

// То же для std::vector. Перевыделения считаем по изменению capacity.
Run fill_std(unsigned int n, bool reserve) {
    std::size_t final_cap = 0;
    long faults = 0;
    double seconds = time_std(n, reserve, final_cap, faults);
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
    return {seconds, re, moved, peak, static_cast<unsigned long long>(final_cap), faults};
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

// Состояние развёртки одной стратегии: по последней измеренной точке прогнозируем следующую.
struct SweepState {
    double last_t = 0;
    unsigned int last_n = 0;
};

// Одна точка (стратегия, n): прогрев + несколько замеров; пропуск, если прогноз > cap.
void measure_point(std::ofstream& f, const std::string& series, const std::string& param, const Strategy& s,
                   unsigned int n, SweepState& st) {
    double predicted = 0;
    if (st.last_n) {
        double r = double(n) / st.last_n;
        predicted = st.last_t * (s.quadratic ? r * r : r);
    }
    if (predicted > g_cap_seconds) {
        f << series << ',' << s.name << ',' << param << ',' << n << ",0,,,,,,,skipped_predicted_" << predicted
          << "s\n";
        std::cerr << "  " << s.name << " n=" << n << " skipped (predicted " << predicted << " s)\n";
        return;
    }
    s.fill(std::min(n, 100000u));  // короткий прогрев кода
    int T = trials_for(predicted);
    std::vector<double> ts;
    for (int t = 1; t <= T; ++t) {
        Run r = s.fill(n);
        ts.push_back(r.seconds);
        f << series << ',' << s.name << ',' << param << ',' << n << ',' << t << ',' << r.seconds << ','
          << r.reallocations << ',' << r.moved << ',' << r.peak_elements << ',' << r.final_capacity << ','
          << r.page_faults << ",ok\n";
    }
    st.last_t = median(ts);
    st.last_n = n;
    std::cerr << "  " << s.name << " n=" << n << " median " << st.last_t << " s (" << T << " trials)\n";
    f.flush();
}

// Все стратегии на всех n. Стратегии перемешиваются на каждом n (фиксированный seed), чтобы ни одна
// систематически не шла первой: время зависит от состояния распределителя памяти, оставленного
// предыдущими замерами (см. отчёт, раздел про page faults).
void sweep_interleaved(std::ofstream& f, const std::string& series, const std::vector<Strategy>& ss,
                       const std::vector<std::string>& params, const std::vector<unsigned int>& ns) {
    std::vector<SweepState> states(ss.size());
    std::vector<std::size_t> order(ss.size());
    for (std::size_t i = 0; i < order.size(); ++i) order[i] = i;
    std::mt19937 rng(20261023u);
    for (unsigned int n : ns) {
        std::shuffle(order.begin(), order.end(), rng);
        for (std::size_t i : order) measure_point(f, series, params[i], ss[i], n, states[i]);
    }
}

// Прогрев распределителя: выделить, заполнить и освободить блок чуть меньше 32 МБ.
// После этого glibc поднимает порог mmap до размера этого блока, и все стратегии стартуют
// в одинаковом состоянии кучи (иначе первая измеряемая стратегия платит лишние page faults).
void heap_warmup() {
    std::vector<char> w(30u << 20, 1);
    g_sink = g_sink + static_cast<unsigned char>(w[12345]);
}

std::ofstream open_runs(const std::string& path) {
    std::ofstream f(path);
    f << std::setprecision(17);
    f << "series,strategy,param,n,trial,seconds,reallocations,moved_elements,peak_elements,final_capacity,page_faults,status\n";
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

    heap_warmup();

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
        sweep_interleaved(f, "strategies", ss, std::vector<std::string>(ss.size(), ""), ns);
    }

    if (mode == "factor" || mode == "all") {
        std::cerr << "factor sweep\n";
        std::ofstream f = open_runs(dir + "/factor.csv");
        // Время одного заполнения сильно зависит от того, где n оказалось относительно ближайшего
        // перевыделения, поэтому для каждого множителя берём несколько n и затем усредняем нс/элемент.
        const std::vector<unsigned int> ns = {2000000, 4000000, 6000000, 8000000, 10000000};
        std::vector<double> fs = {1.02, 1.05, 1.1, 1.2, 1.3, 1.4, 1.5, 1.618, 1.75, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0, 16.0};
        std::vector<Strategy> ss;
        std::vector<std::string> params;
        for (double k : fs) {
            char buf[32];
            std::snprintf(buf, sizeof buf, "%g", k);
            ss.push_back(sub("x" + std::string(buf), Growth::mul(k)));
            params.push_back(buf);
        }
        sweep_interleaved(f, "factor", ss, params, ns);
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
                    f << "step_n" << n << ",+" << st << ',' << param << ',' << n << ",0,,,,,,,skipped_predicted_"
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
                      << r.final_capacity << ',' << r.page_faults << ",ok\n";
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
