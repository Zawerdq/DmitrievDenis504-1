// main.cpp — подготовка данных, вызовы исследуемых функций и измерения.
//
// Запуск:
//   research_<opt>_<N> A <opt_label> <out_dir> [--scalar] [опции]   — опыт A для BLOCK_SIZE=N
//   research_<opt>_<N> B <opt_label> <out_dir> [опции]              — опыт B (время + счётчики памяти)
// Опции:
//   --seed S       начальное значение генератора (по умолчанию DEFAULT_SEED)
//   --input FILE   брать текст из файла (записи по строкам) вместо генератора
//   --inputs M     число различных входов каждой длины, степень двойки (по умолчанию 8)
//   --trials T     число измерений каждого условия (по умолчанию 7, минимум 5)
//   --target-ms X  минимальная длительность одной серии при подборе повторений (по умолчанию 40)
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <memory>
#include <random>
#include <string>
#include <vector>

#include "inputs.h"
#include "text.h"

namespace {

using Clock = std::chrono::steady_clock;

struct Options {
    std::string experiment;
    std::string opt_label;
    std::string out_dir;
    bool scalar = false;
    std::uint32_t seed = DEFAULT_SEED;
    std::string input_file;
    std::size_t inputs = 8;
    int trials = 7;
    double target_ms = 40.0;
};

[[noreturn]] void die(const std::string& msg) {
    std::cerr << "error: " << msg << "\n";
    std::exit(2);
}

Options parse(int argc, char** argv) {
    if (argc < 4) die("usage: research <A|B> <opt_label> <out_dir> [--scalar] [--seed S] [--input FILE] "
                      "[--inputs M] [--trials T] [--target-ms X]");
    Options o;
    o.experiment = argv[1];
    o.opt_label = argv[2];
    o.out_dir = argv[3];
    for (int i = 4; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) die("missing value for " + a);
            return argv[++i];
        };
        if (a == "--scalar") o.scalar = true;
        else if (a == "--seed") o.seed = static_cast<std::uint32_t>(std::stoul(next()));
        else if (a == "--input") o.input_file = next();
        else if (a == "--inputs") o.inputs = std::stoul(next());
        else if (a == "--trials") o.trials = std::stoi(next());
        else if (a == "--target-ms") o.target_ms = std::stod(next());
        else die("unknown option " + a);
    }
    if (o.trials < 5) die("need at least 5 trials");
    if (o.inputs < 2 || (o.inputs & (o.inputs - 1)) != 0)
        die("--inputs must be a power of two >= 2 (index = g & (M-1), without division in the timed loop)");
    return o;
}

// Набор строк длины length: из генератора или из файла (записи склеиваются через пробел,
// каждая строка начинается со своего смещения, чтобы входы различались).
std::vector<std::string> make_strings(const Options& o, std::size_t count, std::size_t length) {
    if (o.input_file.empty()) return generate_strings(count, length, o.seed);
    std::vector<std::string> lines;
    if (!read_lines(o.input_file, lines)) die("cannot read " + o.input_file);
    std::string pool;
    for (auto& l : lines) { pool += l; pool += ' '; }
    if (pool.size() < 2) die("input file is too short");
    std::vector<std::string> res;
    for (std::size_t k = 0; k < count; ++k) {
        std::string s(length, ' ');
        std::size_t off = (k * 7919) % pool.size();
        for (std::size_t i = 0; i < length; ++i) s[i] = pool[(off + i) % pool.size()];
        res.push_back(std::move(s));
    }
    return res;
}

inline unsigned long long fold(const Stats& s) { return s.words * 1000003ull + s.sum; }

// ------------------------------------------------------------------ CSV
class TimeCsv {
public:
    explicit TimeCsv(const std::string& path) : f_(path) {
        if (!f_) die("cannot open " + path);
        f_ << "experiment,length,mode,work,repeats,uses,opt,trial,seconds,result\n";
        f_ << std::setprecision(17);
    }
    struct Row {
        std::string experiment;
        std::size_t length;
        std::string mode, work;
        std::size_t repeats, uses;
        std::string opt;
        int trial;
        double seconds;
        unsigned long long result;
    };
    void add(const Row& r) { rows_.push_back(r); }
    // Вывод в файл — только после всех измерений, вне таймера.
    void flush() {
        for (auto& r : rows_)
            f_ << r.experiment << ',' << r.length << ',' << r.mode << ',' << r.work << ',' << r.repeats << ','
               << r.uses << ',' << r.opt << ',' << r.trial << ',' << r.seconds << ',' << r.result << '\n';
        rows_.clear();
    }

private:
    std::ofstream f_;
    std::vector<Row> rows_;
};

// ------------------------------------------------------------------ измерение серии
// Одна серия: G вызовов, вход меняется по кругу; результаты складываются в сумму,
// которая сохраняется после остановки таймера.
template <class F>
double run_series(F&& call, std::size_t G, unsigned long long& result) {
    unsigned long long acc = 0;
    auto t0 = Clock::now();
    for (std::size_t g = 0; g < G; ++g) acc += call(g);
    auto t1 = Clock::now();
    result = acc;
    return std::chrono::duration<double>(t1 - t0).count();
}

// Вариант хранит функцию, запускающую ЦЕЛУЮ серию. Внутренний цикл инстанцируется
// шаблоном run_series для конкретной лямбды, так что косвенный вызов std::function
// происходит один раз на серию, а не на каждый исследуемый вызов.
struct Variant {
    std::string mode;
    std::function<double(std::size_t, unsigned long long&)> series;
};

template <class F>
Variant make_variant(const std::string& mode, F call) {
    return Variant{mode, [call](std::size_t G, unsigned long long& r) { return run_series(call, G, r); }};
}

// Подбор G: удваиваем, пока самая медленная (первая) из вариаций не займёт target_ms.
std::size_t calibrate(const Variant& v, double target_ms) {
    std::size_t G = 16;
    unsigned long long dummy = 0;
    for (;;) {
        double t = v.series(G, dummy);
        if (t * 1000.0 >= target_ms || G >= (std::size_t(1) << 34)) return G;
        G *= 2;
    }
}

// Прогрев + trials измерений каждого варианта в перемешанном порядке.
// Проверяет, что все варианты на одной последовательности дали одинаковую сумму результатов.
void measure_group(TimeCsv& csv, std::mt19937& order_rng, const Options& o, const std::string& experiment,
                   std::size_t length, const std::string& work, std::size_t uses, std::vector<Variant>& vars,
                   std::size_t G) {
    unsigned long long ref_result = 0;
    for (std::size_t i = 0; i < vars.size(); ++i) {  // прогрев
        unsigned long long r = 0;
        vars[i].series(G, r);
        if (i == 0) ref_result = r;
        else if (r != ref_result) die("result mismatch in warm-up: " + experiment + " " + vars[i].mode);
    }
    std::vector<std::size_t> order(vars.size());
    for (std::size_t i = 0; i < order.size(); ++i) order[i] = i;
    for (int trial = 1; trial <= o.trials; ++trial) {
        std::shuffle(order.begin(), order.end(), order_rng);
        for (std::size_t idx : order) {
            unsigned long long r = 0;
            double sec = vars[idx].series(G, r);
            if (r != ref_result) die("result mismatch: " + experiment + " " + vars[idx].mode);
            csv.add({experiment, length, vars[idx].mode, work, G, uses, o.opt_label, trial, sec, r});
        }
    }
    std::cerr << "  " << experiment << " L=" << length << " " << work << " G=" << G << " done\n";
}

// ================================================================== Опыт A
void experiment_a(const Options& o) {
    TimeCsv csv(o.out_dir + "/A_" + o.opt_label + "_" + std::to_string(BLOCK_SIZE) + ".csv");
    std::mt19937 order_rng(o.seed + BLOCK_SIZE);
    const std::size_t M = o.inputs;
    const std::size_t mask = M - 1;  // вход номер g & mask: смена входа без деления в замеряемом цикле

    // ---- скаляр: точка отсчёта ----
    if (o.scalar) {
        std::vector<unsigned int> xs(M);
        for (std::size_t i = 0; i < M; ++i) xs[i] = static_cast<unsigned int>(i + 1);  // небольшие значения
        for (std::size_t i = 0; i < M; ++i)
            if (scalar_val(xs[i]) != scalar_ref(xs[i]) || scalar_ref(xs[i]) != scalar_ptr(&xs[i]))
                die("scalar check failed");
        std::vector<Variant> v = {
            make_variant("value", [&](std::size_t g) { return (unsigned long long)scalar_val(xs[g & mask]); }),
            make_variant("ref", [&](std::size_t g) { return (unsigned long long)scalar_ref(xs[g & mask]); }),
            make_variant("ptr", [&](std::size_t g) { return (unsigned long long)scalar_ptr(&xs[g & mask]); }),
        };
        std::size_t G = calibrate(v[0], o.target_ms);
        measure_group(csv, order_rng, o, "scalar", 0, "short", 1, v, G);
    }

    // ---- Block: символы внутри объекта ----
    {
        auto strs = make_strings(o, M, block_length());
        std::vector<Block> blocks(M);  // живут весь опыт; полностью инициализированы
        for (std::size_t i = 0; i < M; ++i) fill_block(blocks[i], strs[i]);
        for (std::size_t i = 0; i < M; ++i) {  // отдельная проверка каждого результата
            Stats s = block_full_ref(blocks[i]);
            if (!(s == block_full_val(blocks[i]) && s == block_full_ptr(&blocks[i]) &&
                  s == text_full_ref(as_text(blocks[i]))))
                die("Block full check failed");
            if (block_first_val(blocks[i]) != block_first_ptr(&blocks[i])) die("Block first check failed");
        }
        std::vector<Variant> shortv = {
            make_variant("value", [&](std::size_t g) { return (unsigned long long)block_first_val(blocks[g & mask]); }),
            make_variant("ref", [&](std::size_t g) { return (unsigned long long)block_first_ref(blocks[g & mask]); }),
            make_variant("ptr", [&](std::size_t g) { return (unsigned long long)block_first_ptr(&blocks[g & mask]); }),
        };
        std::vector<Variant> fullv = {
            make_variant("value", [&](std::size_t g) { return fold(block_full_val(blocks[g & mask])); }),
            make_variant("ref", [&](std::size_t g) { return fold(block_full_ref(blocks[g & mask])); }),
            make_variant("ptr", [&](std::size_t g) { return fold(block_full_ptr(&blocks[g & mask])); }),
        };
        measure_group(csv, order_rng, o, "Block", block_length(), "short", 1, shortv,
                      calibrate(shortv[0], o.target_ms));
        measure_group(csv, order_rng, o, "Block", block_length(), "full", 1, fullv,
                      calibrate(fullv[0], o.target_ms));
    }

    // ---- Text: символы отдельно, в объекте только адрес и длина ----
    {
        const std::size_t L = block_length();  // 15, 1023, 16383
        std::vector<std::string> owners = make_strings(o, M, L);  // владельцы символов живут весь опыт
        std::vector<Text> texts(M);
        for (std::size_t i = 0; i < M; ++i) texts[i] = Text{owners[i].data(), owners[i].size()};
        for (std::size_t i = 0; i < M; ++i) {
            Stats s = text_full_ref(texts[i]);
            if (!(s == text_full_val(texts[i]) && s == text_full_ptr(&texts[i]))) die("Text check failed");
        }
        std::vector<Variant> shortv = {
            make_variant("value", [&](std::size_t g) { return (unsigned long long)text_first_val(texts[g & mask]); }),
            make_variant("ref", [&](std::size_t g) { return (unsigned long long)text_first_ref(texts[g & mask]); }),
            make_variant("ptr", [&](std::size_t g) { return (unsigned long long)text_first_ptr(&texts[g & mask]); }),
        };
        std::vector<Variant> fullv = {
            make_variant("value", [&](std::size_t g) { return fold(text_full_val(texts[g & mask])); }),
            make_variant("ref", [&](std::size_t g) { return fold(text_full_ref(texts[g & mask])); }),
            make_variant("ptr", [&](std::size_t g) { return fold(text_full_ptr(&texts[g & mask])); }),
        };
        measure_group(csv, order_rng, o, "Text", L, "short", 1, shortv, calibrate(shortv[0], o.target_ms));
        measure_group(csv, order_rng, o, "Text", L, "full", 1, fullv, calibrate(fullv[0], o.target_ms));
    }
    csv.flush();

    // sizeof объектов (что именно передаётся по значению)
    std::ofstream sz(o.out_dir + "/sizes_" + o.opt_label + "_" + std::to_string(BLOCK_SIZE) + ".csv");
    sz << "type,length,sizeof_bytes\n";
    sz << "unsigned int,0," << sizeof(unsigned int) << "\n";
    sz << "Block," << block_length() << "," << sizeof(Block) << "\n";
    sz << "Text," << block_length() << "," << sizeof(Text) << "\n";
    sz << "pointer,0," << sizeof(const Block*) << "\n";
}

// ================================================================== Опыт B
struct Counters {
    unsigned long long allocations = 0;  // вызовов new[] для исследуемых копий
    unsigned long long copied_bytes = 0; // перенесённых полезных байтов (без '\0')
    unsigned long long current = 0;      // сейчас выделено (элементов char, с '\0')
    unsigned long long peak = 0;         // максимум current
};

// Копия, учтённая (Count=true) или нет (Count=false) в счётчиках.
// Счётчики обновляются во время реальных действий с буферами.
template <bool Count>
inline char* make_copy(Text t, Counters& c) {
    char* p = clone_text(t);  // new char[L+1], L символов, отдельно '\0'
    if constexpr (Count) {
        ++c.allocations;
        c.copied_bytes += t.size;
        c.current += t.size + 1;
        if (c.current > c.peak) c.peak = c.current;
    }
    return p;
}

template <bool Count>
inline void release_copy(char* p, std::size_t L, Counters& c) {
    if constexpr (Count) c.current -= L + 1;
    delete[] p;
    (void)L;
    (void)c;
}

enum class BMode { borrow, copy_each, copy_once };
const char* bmode_name(BMode m) {
    switch (m) {
        case BMode::borrow: return "borrow";
        case BMode::copy_each: return "copy_each";
        case BMode::copy_once: return "copy_once";
    }
    return "?";
}

// Одна группа: строка texts[g & mask] анализируется ровно K раз полным обработчиком.
template <bool Count>
unsigned long long run_group(BMode mode, const Text& src, std::size_t K, Counters& c) {
    unsigned long long acc = 0;
    switch (mode) {
        case BMode::borrow:
            for (std::size_t k = 0; k < K; ++k) acc += fold(text_full_val(src));
            break;
        case BMode::copy_each:
            for (std::size_t k = 0; k < K; ++k) {
                char* p = make_copy<Count>(src, c);
                acc += fold(text_full_val(Text{p, src.size}));
                release_copy<Count>(p, src.size, c);
            }
            break;
        case BMode::copy_once: {
            char* p = make_copy<Count>(src, c);
            for (std::size_t k = 0; k < K; ++k) acc += fold(text_full_val(Text{p, src.size}));
            release_copy<Count>(p, src.size, c);
            break;
        }
    }
    return acc;
}

// Владелец исходных строк опыта B: массивы в динамической памяти, созданные заранее.
struct Sources {
    std::vector<std::unique_ptr<char[]>> owners;
    std::vector<Text> texts;
};

Sources make_sources(const Options& o, std::size_t L) {
    Sources s;
    for (auto& str : make_strings(o, o.inputs, L)) {
        std::unique_ptr<char[]> p(new char[L + 1]);
        std::memcpy(p.get(), str.data(), L);
        p[L] = '\0';
        s.texts.push_back(Text{p.get(), L});
        s.owners.push_back(std::move(p));
    }
    return s;
}

void experiment_b(const Options& o) {
    TimeCsv csv(o.out_dir + "/B_" + o.opt_label + ".csv");
    std::ofstream cnt(o.out_dir + "/B_counters.csv");
    cnt << "length,repeats,uses,mode,allocations,copied_bytes,peak_extra_bytes\n";
    std::ofstream pred(o.out_dir + "/B_counters_check.csv");
    pred << "length,repeats,uses,mode,pred_allocations,pred_copied_bytes,pred_peak_extra_bytes,"
            "allocations,copied_bytes,peak_extra_bytes,match\n";

    std::mt19937 order_rng(o.seed + 77);
    const std::vector<std::size_t> lengths = {15, 1023, 16383};
    const std::vector<std::size_t> Ks = {1, 10, 100};
    const BMode modes[] = {BMode::borrow, BMode::copy_each, BMode::copy_once};

    for (std::size_t L : lengths) {
        Sources src = make_sources(o, L);
        const std::size_t mask = src.texts.size() - 1;
        for (std::size_t K : Ks) {
            std::vector<Variant> vars;
            for (BMode m : modes) {
                vars.push_back(make_variant(bmode_name(m), [&src, mask, m, K](std::size_t g) {
                    Counters unused;  // во временном прогоне счётчики отключены (Count=false)
                    return run_group<false>(m, src.texts[g & mask], K, unused);
                }));
            }
            // G подбирается по самому дорогому режиму (copy_each) и фиксируется для всех трёх.
            std::size_t G = calibrate(vars[1], o.target_ms);
            measure_group(csv, order_rng, o, "copy", L, "full", K, vars, G);

            // Отдельный прогон той же последовательности действий — со счётчиками.
            for (BMode m : modes) {
                Counters c;
                unsigned long long acc = 0;
                for (std::size_t g = 0; g < G; ++g) acc += run_group<true>(m, src.texts[g & mask], K, c);
                if (c.current != 0) die("leak in counted run");
                unsigned long long pa = 0, pc = 0, pp = 0;
                if (m == BMode::copy_each) { pa = G * K; pc = G * K * L; pp = L + 1; }
                if (m == BMode::copy_once) { pa = G; pc = G * L; pp = L + 1; }
                bool ok = pa == c.allocations && pc == c.copied_bytes && pp == c.peak;
                cnt << L << ',' << G << ',' << K << ',' << bmode_name(m) << ',' << c.allocations << ','
                    << c.copied_bytes << ',' << c.peak << '\n';
                pred << L << ',' << G << ',' << K << ',' << bmode_name(m) << ',' << pa << ',' << pc << ',' << pp
                     << ',' << c.allocations << ',' << c.copied_bytes << ',' << c.peak << ','
                     << (ok ? "yes" : "NO") << '\n';
                if (!ok) std::cerr << "  prediction mismatch for L=" << L << " K=" << K << " " << bmode_name(m) << "\n";
                (void)acc;
            }
        }
    }
    csv.flush();
}

}  // namespace

int main(int argc, char** argv) {
    Options o = parse(argc, argv);
    std::cerr << "BLOCK_SIZE=" << BLOCK_SIZE << " sizeof(Block)=" << sizeof(Block) << " sizeof(Text)=" << sizeof(Text)
              << " opt=" << o.opt_label << "\n";
    if (o.experiment == "A") experiment_a(o);
    else if (o.experiment == "B") experiment_b(o);
    else die("experiment must be A or B");
    return 0;
}
