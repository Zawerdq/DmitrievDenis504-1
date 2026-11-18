// Проверки корректности subvector<T>.
// Сборка: g++ -std=c++17 -O1 -g -fsanitize=address,undefined tests.cpp -o build/tests && ./build/tests
#include <cstdio>
#include <random>
#include <string>
#include <vector>

#include "subvector.h"

static int failed = 0, passed = 0;
#define CHECK(cond) do { if (cond) ++passed; else { ++failed; std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); } } while (0)

// Тип, который считает живые объекты: после каждого теста их должно быть ровно 0.
struct Counted {
    static int alive;
    int v;
    Counted(int x = 0) : v(x) { ++alive; }
    Counted(const Counted& o) : v(o.v) { ++alive; }
    Counted(Counted&& o) noexcept : v(o.v) { ++alive; }
    Counted& operator=(const Counted&) = default;
    ~Counted() { --alive; }
};
int Counted::alive = 0;

static void basic(Realloc how) {
    subvector<int> v(Growth::mul(2.0), how);
    CHECK(v.get_data() == nullptr && v.get_size() == 0 && v.get_capacity() == 0);
    CHECK(v.pop_back() == 0 && v.get_size() == 0);           // пустой -> 0
    v.clear(); v.shrink_to_fit();
    CHECK(v.get_data() == nullptr && v.get_capacity() == 0);

    for (int i = 0; i < 1000; ++i) CHECK(v.push_back(3 * i));
    CHECK(v.get_size() == 1000 && v.get_capacity() == 1024); // x2: 1,2,4,...,1024
    bool same = true;
    for (unsigned i = 0; i < 1000; ++i) same = same && v[i] == int(3 * i);
    CHECK(same);
    CHECK(v.pop_back() == 2997 && v.get_size() == 999 && v.get_capacity() == 1024);

    CHECK(v.resize(2000) && v.get_capacity() == 2000 && v.get_size() == 999 && v[998] == 2994);
    CHECK(v.resize(10) && v.get_capacity() == 10 && v.get_size() == 10 && v[9] == 27);   // обрезка
    CHECK(v.push_back(7) && v.get_size() == 11 && v.get_capacity() == 20 && v[10] == 7);
    v.shrink_to_fit();
    CHECK(v.get_capacity() == 11 && v.get_size() == 11 && v[0] == 0);
    v.clear();
    CHECK(v.get_size() == 0 && v.get_capacity() == 11);      // clear память не трогает
    CHECK(v.push_back(5) && v[0] == 5);
    CHECK(v.resize(0) && v.get_data() == nullptr && v.get_size() == 0);
    CHECK(v.push_back(9) && v.get_size() == 1 && v.get_capacity() == 1);
}

static void sequences() {
    Growth g = Growth::add(10);
    CHECK(next_capacity(g, 0) == 10 && next_capacity(g, 10) == 20);
    CHECK(next_capacity(Growth::add(100), 100) == 200);
    g = Growth::mul(1.5);
    unsigned int c = 0, expect[] = {1, 2, 3, 5, 8, 12, 18, 27, 41, 62};
    bool ok = true;
    for (unsigned int e : expect) { c = next_capacity(g, c); ok = ok && c == e; }
    CHECK(ok);
    g.factor = 1.01;
    CHECK(next_capacity(g, 1) == 2 && next_capacity(g, 100) == 101);   // рост хотя бы на 1
    g.factor = 1e300;
    CHECK(next_capacity(g, 5) == 4294967295u);                         // без переполнения и UB
    CHECK(next_capacity(Growth::add(10), 4294967290u) == 4294967295u);
    CHECK(Growth::mul(0.5).factor == 2.0 && Growth::mul(0.0 / 0.0).factor == 2.0);   // недопустимые -> 2
    CHECK(Growth::add(0).step == 1);

    subvector<int> std_like;                                           // по умолчанию x2, как std::vector
    for (int i = 0; i < 129; ++i) std_like.push_back(i);
    CHECK(std_like.get_capacity() == 256);
}

// Случайные операции, сравнение с std::vector после КАЖДОЙ операции (всё содержимое).
template <class T, class Make>
static void random_against_std(Realloc how, Growth g, Make make) {
    subvector<T> v(g, how);
    std::vector<T> ref;
    std::mt19937 rng(2026);
    bool ok = true;
    for (int step = 0; step < 20000 && ok; ++step) {
        unsigned r = rng() % 100;
        if (r < 60) { T x = make(int(rng() % 1000)); ok = v.push_back(x); ref.push_back(x); }
        else if (r < 90) { T e = ref.empty() ? T() : ref.back(); if (!ref.empty()) ref.pop_back(); ok = v.pop_back() == e; }
        else if (r < 94) { v.shrink_to_fit(); ok = v.get_capacity() == v.get_size(); }
        else if (r < 98) { unsigned c = rng() % 300; ok = v.resize(c) && v.get_capacity() == c; if (ref.size() > c) ref.resize(c); }
        else { unsigned c = v.get_capacity(); v.clear(); ref.clear(); ok = v.get_capacity() == c; }
        ok = ok && v.get_size() == ref.size() && v.get_capacity() >= v.get_size();
        for (unsigned i = 0; ok && i < v.get_size(); ++i) ok = v[i] == ref[i];
    }
    CHECK(ok);
}

static void non_trivial() {
    {   // строки: память владеется элементами, ASan ловит утечки и двойное освобождение
        subvector<std::string> v;
        for (int i = 0; i < 500; ++i) v.push_back(std::string(30, char('a' + i % 26)) + std::to_string(i));
        CHECK(v.get_size() == 500 && v[499] == std::string(30, 'f') + "499");
        CHECK(v.pop_back() == std::string(30, 'f') + "499");
        v.resize(10);
        CHECK(v.get_size() == 10 && v[9].back() == '9');
        subvector<std::string> copy(v);                      // глубокая копия
        copy[0] = "changed";
        CHECK(v[0] != "changed" && copy.get_capacity() == 10);
        subvector<std::string> moved(std::move(copy));      // перемещение забирает блок
        CHECK(copy.get_size() == 0 && copy.get_data() == nullptr && moved[0] == "changed");
        v = moved;                                           // присваивание копией
        CHECK(v[0] == "changed" && moved[0] == "changed");
        v.push_back(v[0]);                                   // ссылка на свой элемент при перевыделении
        CHECK(v.get_size() == 11 && v[10] == "changed");
    }
    {   // счётчик живых объектов: каждый созданный уничтожен ровно один раз
        {
            subvector<Counted> v(Growth::add(3));
            for (int i = 0; i < 100; ++i) v.push_back(Counted(i));
            CHECK(Counted::alive == 100);
            v.pop_back(); v.pop_back();
            CHECK(Counted::alive == 98);
            v.resize(50);
            CHECK(Counted::alive == 50);
            v.shrink_to_fit(); v.clear();
            CHECK(Counted::alive == 0 && v.get_capacity() == 50);
            for (int i = 0; i < 7; ++i) v.push_back(Counted(i));
        }
        CHECK(Counted::alive == 0);                          // деструктор вектора
    }
    {   // для нетривиальных T быстрые способы перевыделения не включаются
        subvector<std::string> v(Growth::mul(2), Realloc::CRealloc);
        for (int i = 0; i < 100; ++i) v.push_back(std::to_string(i));
        CHECK(v[99] == "99");
    }
}

int main() {
    for (Realloc h : {Realloc::NewLoop, Realloc::NewMemcpy, Realloc::CRealloc}) {
        basic(h);
        for (Growth g : {Growth::add(10), Growth::add(100), Growth::mul(1.5), Growth::mul(2.0)})
            random_against_std<int>(h, g, [](int x) { return x; });
    }
    for (Growth g : {Growth::add(10), Growth::mul(1.5), Growth::mul(2.0)})
        random_against_std<std::string>(Realloc::NewLoop, g, [](int x) { return std::string(20, 'x') + std::to_string(x); });
    sequences();
    non_trivial();
    std::printf("%d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
