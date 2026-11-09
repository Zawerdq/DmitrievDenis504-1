// Все опыты лабораторной. Запуск:
//   ./bench            - все части подряд
//   ./bench capacity   - как растёт capacity у std::vector, поведение конструкторов
//   ./bench strategies - сравнение стратегий +10, +100, x1.5, x2 и std::vector
//   ./bench factor     - время заполнения в зависимости от множителя
//   ./bench step       - время заполнения в зависимости от прибавляемой константы
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

#include "subvector.h"

const int TRIALS = 5;              // измерений каждой точки
const double SLOW_SECONDS = 2.0;   // если один замер дольше, точка измеряется один раз

double get_time() {
    return std::chrono::duration_cast<std::chrono::microseconds>(
               std::chrono::steady_clock::now().time_since_epoch()).count() / 1e6;
}

// Время заполнения subvector n элементами. Создание и уничтожение вектора в замер не входят.
// guard использует результат, чтобы работа была нужна программе.
double time_subvector(unsigned int n, bool multiply, double value, long long& guard) {
    subvector v;
    if (multiply) v.set_growth_factor(value);
    else v.set_growth_step((unsigned int)value);

    double start = get_time();
    for (unsigned int i = 0; i < n; ++i) {
        v.push_back((int)i);
    }
    double finish = get_time();

    guard = (long long)v.get_size() + v.get(0) + v.get(n / 2) + v.get(n - 1);
    return finish - start;
}

double time_std_vector(unsigned int n, long long& guard) {
    std::vector<int> v;

    double start = get_time();
    for (unsigned int i = 0; i < n; ++i) {
        v.push_back((int)i);
    }
    double finish = get_time();

    guard = (long long)v.size() + v[0] + v[n / 2] + v[n - 1];
    return finish - start;
}

// Проход без таймера: сколько было перевыделений, сколько элементов перенесено, какая ёмкость в конце.
void count_subvector(unsigned int n, bool multiply, double value, unsigned long long& reallocations,
                     unsigned long long& copied, unsigned int& final_capacity) {
    subvector v;
    if (multiply) v.set_growth_factor(value);
    else v.set_growth_step((unsigned int)value);

    reallocations = 0;
    copied = 0;
    for (unsigned int i = 0; i < n; ++i) {
        unsigned int before = v.get_capacity();
        v.push_back((int)i);
        if (v.get_capacity() != before) {
            ++reallocations;
            copied += i;          // в новый массив перенесены i старых элементов
        }
    }
    final_capacity = v.get_capacity();
}

// ======================= 1. Исследование std::vector =======================

int part_capacity() {
    const unsigned int N = 10000000;

    std::ofstream file("data/capacity.csv");
    if (!file) return 1;
    file << "container,size,capacity\n";

    // Записываем точку каждый раз, когда ёмкость изменилась.
    std::vector<unsigned int> std_caps;
    {
        std::vector<int> v;
        file << "std::vector,0," << v.capacity() << '\n';
        for (unsigned int i = 0; i < N; ++i) {
            std::size_t before = v.capacity();
            v.push_back((int)i);
            if (v.capacity() != before) {
                file << "std::vector," << v.size() << ',' << v.capacity() << '\n';
                std_caps.push_back((unsigned int)v.capacity());
            }
        }
    }

    // То же для subvector с множителями 2 и 1.5: с какой последовательностью совпадёт std::vector?
    const double FACTORS[2] = {2.0, 1.5};
    const char* NAMES[2] = {"subvector x2", "subvector x1.5"};
    for (int f = 0; f < 2; ++f) {
        subvector v;
        v.set_growth_factor(FACTORS[f]);
        std::vector<unsigned int> caps;
        file << NAMES[f] << ",0,0\n";
        for (unsigned int i = 0; i < N; ++i) {
            unsigned int before = v.get_capacity();
            v.push_back((int)i);
            if (v.get_capacity() != before) {
                file << NAMES[f] << ',' << v.get_size() << ',' << v.get_capacity() << '\n';
                caps.push_back(v.get_capacity());
            }
        }
        std::cout << "std::vector: " << std_caps.size() << " изменений ёмкости, " << NAMES[f] << ": "
                  << caps.size() << ", последовательности "
                  << (caps == std_caps ? "совпадают" : "не совпадают") << '\n';
    }

    // Что дают разные конструкторы и методы std::vector.
    std::ofstream ctor("data/std_constructors.csv");
    if (!ctor) return 1;
    ctor << "case,size,capacity\n";

    std::vector<int> a;
    ctor << "vector<int> a;," << a.size() << ',' << a.capacity() << '\n';
    std::vector<int> b(10);
    ctor << "vector<int> b(10);," << b.size() << ',' << b.capacity() << '\n';
    std::vector<int> c(10, 7);
    ctor << "vector<int> c(10, 7);," << c.size() << ',' << c.capacity() << '\n';
    std::vector<int> d = {1, 2, 3};
    ctor << "vector<int> d = {1, 2, 3};," << d.size() << ',' << d.capacity() << '\n';
    b.push_back(1);
    ctor << "b.push_back(1) при size == capacity == 10," << b.size() << ',' << b.capacity() << '\n';
    std::vector<int> e(b);
    ctor << "vector<int> e(b); (копия b)," << e.size() << ',' << e.capacity() << '\n';
    a.reserve(100);
    ctor << "a.reserve(100);," << a.size() << ',' << a.capacity() << '\n';
    a.resize(5);
    ctor << "a.resize(5);," << a.size() << ',' << a.capacity() << '\n';
    b.pop_back();
    ctor << "b.pop_back();," << b.size() << ',' << b.capacity() << '\n';
    b.clear();
    ctor << "b.clear();," << b.size() << ',' << b.capacity() << '\n';
    b.shrink_to_fit();
    ctor << "b.shrink_to_fit(); после clear," << b.size() << ',' << b.capacity() << '\n';

    std::cout << "часть capacity готова\n";
    return 0;
}

// ======================= 2. Сравнение стратегий =======================

const int STRATEGIES = 5;
const char* STRATEGY_NAMES[STRATEGIES] = {"+10", "+100", "x1.5", "x2", "std::vector"};

double time_strategy(int s, unsigned int n, long long& guard) {
    if (s == 0) return time_subvector(n, false, 10, guard);
    if (s == 1) return time_subvector(n, false, 100, guard);
    if (s == 2) return time_subvector(n, true, 1.5, guard);
    if (s == 3) return time_subvector(n, true, 2.0, guard);
    return time_std_vector(n, guard);
}

// Измерить стратегии с номерами first..4 при данном n и записать строки в файл.
void measure_strategies(std::ofstream& file, int first, unsigned int n) {
    int count = STRATEGIES - first;
    bool slow[STRATEGIES] = {false, false, false, false, false};
    for (int trial = 1; trial <= TRIALS; ++trial) {
        for (int j = 0; j < count; ++j) {
            int s = first + (trial + j) % count;      // порядок стратегий меняется
            if (slow[s]) continue;                    // долгую точку не повторяем
            long long guard = 0;
            double seconds = time_strategy(s, n, guard);
            if (seconds > SLOW_SECONDS) slow[s] = true;
            file << STRATEGY_NAMES[s] << ',' << n << ',' << trial << ',' << seconds << ',' << guard << '\n';
        }
    }
}

int part_strategies() {
    std::ofstream file("data/strategies.csv");
    if (!file) return 1;
    file << std::setprecision(17);
    file << "strategy,n,trial,seconds,result\n";

    long long guard = 0;
    for (int s = 0; s < STRATEGIES; ++s) time_strategy(s, 100000, guard);   // прогрев

    // Все пять стратегий: от 100 тысяч до 1 миллиона элементов.
    for (unsigned int n = 100000; n <= 1000000; n += 100000) {
        measure_strategies(file, 0, n);
        std::cout << "strategies: n = " << n << '\n';
    }
    // От 2 до 10 миллионов: x1.5, x2 и std::vector.
    // Стратегии +10 и +100 здесь заняли бы от минут до часов на одну точку (см. отчёт),
    // поэтому +100 измеряется только при 2 и 3 миллионах - для проверки прогноза.
    for (unsigned int n = 2000000; n <= 10000000; n += 1000000) {
        measure_strategies(file, n <= 3000000 ? 1 : 2, n);
        std::cout << "strategies: n = " << n << '\n';
    }
    return 0;
}

// ======================= 3. Наилучшая стратегия =======================

// Общая часть двух развёрток: по множителю (multiply = true) и по слагаемому (multiply = false).
// Каждое значение параметра измеряется для каждого n из массива ns.
int sweep(const char* name, bool multiply, const double* values, int count, const unsigned int* ns,
          int n_count) {
    std::ofstream file(std::string("data/") + name + ".csv");
    std::ofstream counts(std::string("data/") + name + "_counts.csv");
    if (!file || !counts) return 1;
    file << name << ",n,trial,seconds,result\n";
    counts << name << ",n,reallocations,copied_elements,final_capacity\n";

    long long guard = 0;
    time_subvector(ns[0], true, 2.0, guard);   // прогрев

    for (int k = 0; k < n_count; ++k) {
        unsigned int n = ns[k];
        std::vector<bool> slow(count, false);
        for (int trial = 1; trial <= TRIALS; ++trial) {
            for (int j = 0; j < count; ++j) {
                int i = trial % 2 == 1 ? j : count - 1 - j;   // чередуем направление обхода
                if (slow[i]) continue;                        // долгую точку не повторяем
                double seconds = time_subvector(n, multiply, values[i], guard);
                if (seconds > SLOW_SECONDS) slow[i] = true;
                file << std::setprecision(10) << values[i] << ',' << n << ',' << trial << ','
                     << std::setprecision(17) << seconds << ',' << guard << '\n';
            }
        }

        // Отдельный проход без таймера: перевыделения, перенесённые элементы, итоговая ёмкость.
        for (int i = 0; i < count; ++i) {
            unsigned long long reallocations = 0, copied = 0;
            unsigned int final_capacity = 0;
            count_subvector(n, multiply, values[i], reallocations, copied, final_capacity);
            counts << std::setprecision(10) << values[i] << ',' << n << ',' << reallocations << ','
                   << copied << ',' << final_capacity << '\n';
        }
    }
    std::cout << "часть " << name << " готова\n";
    return 0;
}

int part_factor() {
    const double FACTORS[] = {1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0,
                              2.2, 2.4, 2.6, 2.8, 3.0, 3.5, 4.0};
    // Три разных n: результат зависит от того, где последняя ёмкость окажется относительно n.
    const unsigned int NS[] = {5000000, 7000000, 10000000};
    return sweep("factor", true, FACTORS, 17, NS, 3);
}

int part_step() {
    const double STEPS[] = {10, 20, 50, 100, 200, 500, 1000, 2000, 5000,
                            10000, 20000, 50000, 100000, 200000, 500000, 1000000};
    const unsigned int NS[] = {1000000};
    return sweep("step", false, STEPS, 16, NS, 1);
}

int main(int argc, char* argv[]) {
    std::string part = argc > 1 ? argv[1] : "all";
    int status = 0;
    if (part == "all" || part == "capacity") status += part_capacity();
    if (part == "all" || part == "strategies") status += part_strategies();
    if (part == "all" || part == "factor") status += part_factor();
    if (part == "all" || part == "step") status += part_step();
    return status == 0 ? 0 : 1;
}
