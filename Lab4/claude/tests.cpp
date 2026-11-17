// Проверки корректности. Сборка: g++ -std=c++17 -O1 -g -fsanitize=address,undefined tests.cpp subvector.cpp
#include <cstdio>
#include <random>
#include <vector>

#include "subvector.h"

static int failed = 0, passed = 0;
#define CHECK(cond) do { if (cond) ++passed; else { ++failed; std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); } } while (0)

static void basic(Realloc how) {
    subvector v;
    init(&v);
    set_realloc(&v, how);
    CHECK(v.mas == nullptr && v.top == 0 && v.capacity == 0);
    CHECK(pop_back(&v) == 0 && v.top == 0);                 // пустой -> 0
    clear(&v); shrink_to_fit(&v);
    CHECK(v.mas == nullptr && v.capacity == 0);

    for (int i = 0; i < 1000; ++i) CHECK(push_back(&v, 3 * i));
    CHECK(v.top == 1000 && v.capacity == 1024);              // x2: 1,2,4,...,1024
    bool same = true;
    for (int i = 0; i < 1000; ++i) same = same && v.mas[i] == 3 * i;
    CHECK(same);
    CHECK(pop_back(&v) == 2997 && v.top == 999 && v.capacity == 1024);

    CHECK(resize(&v, 2000) && v.capacity == 2000 && v.top == 999 && v.mas[998] == 2994);
    CHECK(resize(&v, 10) && v.capacity == 10 && v.top == 10 && v.mas[9] == 27);   // обрезка
    CHECK(push_back(&v, 7) && v.top == 11 && v.capacity == 20 && v.mas[10] == 7);
    shrink_to_fit(&v);
    CHECK(v.capacity == 11 && v.top == 11 && v.mas[0] == 0);
    clear(&v);
    CHECK(v.top == 0 && v.capacity == 11);                   // clear память не трогает
    CHECK(push_back(&v, 5) && v.mas[0] == 5);
    CHECK(resize(&v, 0) && v.mas == nullptr && v.top == 0);
    CHECK(push_back(&v, 9) && v.top == 1 && v.capacity == 1);
    destructor(&v);
    CHECK(v.mas == nullptr && v.top == 0 && v.capacity == 0);
    destructor(&v);                                          // повторный вызов безопасен
}

static void sequences() {
    Growth g;
    g.multiply = false; g.step = 10;
    CHECK(next_capacity(g, 0) == 10 && next_capacity(g, 10) == 20);
    g.step = 100;
    CHECK(next_capacity(g, 100) == 200);
    g.multiply = true; g.factor = 1.5;
    unsigned int c = 0, expect[] = {1, 2, 3, 5, 8, 12, 18, 27, 41, 62};
    bool ok = true;
    for (unsigned int e : expect) { c = next_capacity(g, c); ok = ok && c == e; }
    CHECK(ok);
    g.factor = 1.01;
    CHECK(next_capacity(g, 1) == 2 && next_capacity(g, 100) == 101);   // рост хотя бы на 1
    g.factor = 1e300;
    CHECK(next_capacity(g, 5) == 4294967295u);                         // без переполнения
    g.multiply = false; g.step = 10;
    CHECK(next_capacity(g, 4294967290u) == 4294967295u);

    subvector v; init(&v);
    set_growth_factor(&v, 0.5);                              // недопустимый -> 2
    CHECK(v.growth.factor == 2.0);
    set_growth_step(&v, 0);
    CHECK(v.growth.step == 1);
    destructor(&v);
}

// Случайные операции, сравнение с std::vector после КАЖДОЙ операции (всё содержимое).
static void random_against_std(Realloc how, Growth g) {
    subvector v; init(&v); set_realloc(&v, how); v.growth = g;
    std::vector<int> ref;
    std::mt19937 rng(2026);
    bool ok = true;
    for (int step = 0; step < 30000 && ok; ++step) {
        unsigned r = rng() % 100;
        if (r < 60) { int x = int(rng() % 1000); ok = push_back(&v, x); ref.push_back(x); }
        else if (r < 90) { int e = ref.empty() ? 0 : ref.back(); if (!ref.empty()) ref.pop_back(); ok = pop_back(&v) == e; }
        else if (r < 94) { shrink_to_fit(&v); ok = v.capacity == v.top; }
        else if (r < 98) { unsigned c = rng() % 300; ok = resize(&v, c) && v.capacity == c; if (ref.size() > c) ref.resize(c); }
        else { unsigned c = v.capacity; clear(&v); ref.clear(); ok = v.capacity == c; }
        ok = ok && v.top == ref.size() && v.capacity >= v.top;
        for (unsigned i = 0; ok && i < v.top; ++i) ok = v.mas[i] == ref[i];
    }
    CHECK(ok);
    destructor(&v);
}

int main() {
    for (Realloc h : {Realloc::NewLoop, Realloc::NewMemcpy, Realloc::CRealloc}) {
        basic(h);
        Growth a; a.multiply = false; a.step = 10;
        Growth b; b.multiply = false; b.step = 100;
        Growth c; c.factor = 1.5;
        Growth d; d.factor = 2.0;
        for (Growth g : {a, b, c, d}) random_against_std(h, g);
    }
    sequences();
    std::printf("%d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
