// tests.cpp — проверки корректности subvector.
// g++ -std=c++17 -O0 -Wall -Wextra -fsanitize=address,undefined tests.cpp -o tests && ./tests
#include <cstdio>
#include <string>
#include <vector>

#include "subvector.h"

static int checks = 0, failures = 0;
#define CHECK(c)                                                         \
    do {                                                                 \
        ++checks;                                                        \
        if (!(c)) {                                                      \
            ++failures;                                                  \
            std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #c);     \
        }                                                                \
    } while (0)

static void basic(Growth g) {
    subvector<int> v(g);
    CHECK(v.get_size() == 0 && v.get_capacity() == 0);
    CHECK(v.pop_back() == 0);  // пустой -> 0
    for (int i = 0; i < 1000; ++i) CHECK(v.push_back(i));
    CHECK(v.get_size() == 1000 && v.get_capacity() >= 1000);
    bool ok = true;
    for (int i = 0; i < 1000; ++i) ok = ok && v[i] == i;
    CHECK(ok);
    CHECK(v.pop_back() == 999 && v.get_size() == 999);

    unsigned int cap = v.get_capacity();
    v.clear();
    CHECK(v.get_size() == 0 && v.get_capacity() == cap);  // clear не трогает capacity
    for (int i = 0; i < 10; ++i) v.push_back(i * i);
    CHECK(v.get_capacity() == cap);  // повторное использование памяти без перевыделения

    v.shrink_to_fit();
    CHECK(v.get_capacity() == 10 && v.get_size() == 10 && v[9] == 81);

    CHECK(v.resize(100));
    CHECK(v.get_capacity() == 100 && v.get_size() == 10 && v[3] == 9);
    CHECK(v.resize(4));  // обрезание данных
    CHECK(v.get_capacity() == 4 && v.get_size() == 4 && v[3] == 9);
    CHECK(v.pop_back() == 9 && v.pop_back() == 4 && v.pop_back() == 1 && v.pop_back() == 0);
    CHECK(v.pop_back() == 0 && v.get_size() == 0);
    CHECK(v.resize(0) && v.get_capacity() == 0);
    CHECK(v.push_back(7) && v[0] == 7);  // рост из нулевой ёмкости
}

int main() {
    basic(Growth::add(10));
    basic(Growth::add(100));
    basic(Growth::mul(1.5));
    basic(Growth::mul(2.0));
    basic(Growth::mul(1.01));  // множитель близкий к 1 всё равно гарантирует рост

    // Последовательности ёмкостей.
    {
        Growth g = Growth::mul(2.0);
        CHECK(g.next(0) == 1 && g.next(1) == 2 && g.next(8) == 16);
        Growth h = Growth::mul(1.5);
        CHECK(h.next(0) == 1 && h.next(1) == 2 && h.next(2) == 3 && h.next(3) == 5 && h.next(10) == 15);
        Growth a = Growth::add(10);
        CHECK(a.next(0) == 10 && a.next(10) == 20);
        CHECK(Growth::mul(2.0).next(4000000000u) == 0);  // переполнение распознаётся
    }

    // Счётчики перевыделений.
    {
        subvector<int> v(Growth::add(100));
        for (int i = 0; i < 1000; ++i) v.push_back(i);
        CHECK(v.stats().reallocations == 10);
        // перенесено 0 + 100 + ... + 900 = 4500 элементов
        CHECK(v.stats().moved_elements == 4500);
    }

    // Копирование и перемещение.
    {
        subvector<int> a;
        for (int i = 0; i < 5; ++i) a.push_back(i);
        subvector<int> b = a;
        CHECK(b.get_size() == 5 && b.get_capacity() == 5 && b[4] == 4);
        b[0] = 42;
        CHECK(a[0] == 0);  // независимая копия
        subvector<int> c = std::move(b);
        CHECK(c.get_size() == 5 && c[0] == 42 && b.get_size() == 0);
        a = c;
        CHECK(a[0] == 42 && a.get_size() == 5);
    }

    // Шаблон работает не только для int.
    {
        subvector<std::string> s;
        for (int i = 0; i < 100; ++i) s.push_back(std::to_string(i));
        CHECK(s[57] == "57" && s.pop_back() == "99");
        CHECK(subvector<std::string>().pop_back().empty());
    }

    // Сверка с std::vector на случайной последовательности операций.
    {
        subvector<int> v(Growth::mul(1.5));
        std::vector<int> ref;
        unsigned int x = 12345;
        bool same = true;
        for (int step = 0; step < 200000; ++step) {
            x = x * 1103515245u + 12345u;
            unsigned int op = (x >> 16) % 10;
            if (op < 6) { v.push_back(int(x)); ref.push_back(int(x)); }
            else if (op < 9) {
                int r = ref.empty() ? 0 : ref.back();
                if (!ref.empty()) ref.pop_back();
                same = same && v.pop_back() == r;
            } else if (step % 1000 == 0) { v.shrink_to_fit(); }
            same = same && v.get_size() == ref.size();
        }
        for (unsigned int i = 0; i < ref.size(); ++i) same = same && v[i] == ref[i];
        CHECK(same);
    }

    std::printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
