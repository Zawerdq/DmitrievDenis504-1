// Проверки решения DeepSeek (написаны Claude). Чтения элемента по индексу в классе нет,
// поэтому содержимое сверяется через pop_back: в конце каждого прогона объект опустошается
// и выталкиваемые значения сравниваются с эталоном std::vector.
// Сборка: g++ -std=c++17 -O1 -g -fsanitize=address,undefined,float-cast-overflow tests.cpp
#include <cstdio>
#include <limits>
#include <random>
#include <vector>

#include "subvector.hpp"

static int failed = 0, passed = 0;
#define CHECK(c) do { if (c) ++passed; else { ++failed; std::printf("FAIL %d: %s\n", __LINE__, #c); } } while (0)

static bool drain_equal(subvector& v, std::vector<int>& ref) {
    bool ok = v.size() == ref.size();
    while (ok && !ref.empty()) { ok = v.pop_back() == ref.back(); ref.pop_back(); }
    return ok && v.size() == 0 && v.pop_back() == 0;
}

int main() {
    {   // пустой объект и базовые операции
        subvector v;
        CHECK(v.size() == 0 && v.capacity() == 0 && v.pop_back() == 0);
        v.clear(); v.shrink_to_fit();
        CHECK(v.capacity() == 0);
        for (int i = 0; i < 1000; ++i) CHECK(v.push_back(i));
        CHECK(v.size() == 1000 && v.capacity() == 1024);
        CHECK(v.resize(10) && v.size() == 10 && v.capacity() == 10);
        CHECK(v.pop_back() == 9);
        v.shrink_to_fit();
        CHECK(v.capacity() == 9);
        v.clear();
        CHECK(v.size() == 0 && v.capacity() == 9);
        CHECK(v.resize(0) && v.capacity() == 0);
        CHECK(v.push_back(5) && v.pop_back() == 5);
    }
    {   // последовательности ёмкостей
        subvector a(subvector::Strategy::Plus10), b(100u), c(1.5), d(subvector::Strategy::Mul2);
        std::vector<unsigned> ca, cc;
        for (int i = 0; i < 25; ++i) { a.push_back(i); if (ca.empty() || ca.back() != a.capacity()) ca.push_back(a.capacity()); }
        for (int i = 0; i < 101; ++i) b.push_back(i);
        for (int i = 0; i < 40; ++i) { c.push_back(i); if (cc.empty() || cc.back() != c.capacity()) cc.push_back(c.capacity()); }
        CHECK((ca == std::vector<unsigned>{10, 20, 30}));
        CHECK(b.capacity() == 200);
        CHECK((cc == std::vector<unsigned>{1, 2, 3, 5, 8, 12, 18, 27, 41}));   // как у Claude и Codex (ceil)
        for (int i = 0; i < 129; ++i) d.push_back(i);
        CHECK(d.capacity() == 256);
    }
    // случайные операции против std::vector для четырёх стратегий
    for (auto s : {subvector::Strategy::Plus10, subvector::Strategy::Plus100,
                   subvector::Strategy::Mul15, subvector::Strategy::Mul2}) {
        subvector v(s);
        std::vector<int> ref;
        std::mt19937 rng(2026);
        bool ok = true;
        for (int step = 0; step < 30000 && ok; ++step) {
            unsigned r = rng() % 100;
            if (r < 60) { int x = int(rng() % 1000); ok = v.push_back(x); ref.push_back(x); }
            else if (r < 90) { int e = ref.empty() ? 0 : ref.back(); if (!ref.empty()) ref.pop_back(); ok = v.pop_back() == e; }
            else if (r < 94) { v.shrink_to_fit(); ok = v.capacity() == v.size(); }
            else if (r < 98) { unsigned c = rng() % 300; ok = v.resize(c) && v.capacity() == c; if (ref.size() > c) ref.resize(c); }
            else { unsigned c = v.capacity(); v.clear(); ref.clear(); ok = v.capacity() == c; }
            ok = ok && v.size() == ref.size() && v.capacity() >= v.size();
        }
        CHECK(ok);
        CHECK(drain_equal(v, ref));
    }
    {   // недопустимые параметры: класс их не проверяет
        subvector one(1.0), zero(0u);
        for (int i = 0; i < 100; ++i) { one.push_back(i); zero.push_back(i); }
        CHECK(one.capacity() == 100 && zero.capacity() == 100);   // спасает «рост хотя бы на 1»: +1 на каждую вставку
    }
    std::printf("%d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
