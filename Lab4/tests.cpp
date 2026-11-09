// Проверки корректности subvector:
//   g++ -O0 tests.cpp subvector.cpp -o tests && ./tests
#include <iostream>
#include <vector>

#include "subvector.h"

int failed = 0;

void check(bool ok, const char* name) {
    std::cout << (ok ? "[ OK ] " : "[FAIL] ") << name << '\n';
    if (!ok) ++failed;
}

// Тот же генератор, что в лабораторной 3: одинаковая последовательность при каждом запуске.
unsigned int next_random(unsigned int& state) {
    state = state * 1664525u + 1013904223u;
    return state >> 8;
}

int main() {
    // ---- Пустой вектор ----
    {
        subvector v;
        check(v.get_size() == 0 && v.get_capacity() == 0, "конструктор: size 0, capacity 0");
        check(v.pop_back() == 0, "pop_back у пустого возвращает 0");
        check(v.get_size() == 0, "pop_back у пустого не меняет size");
        v.clear();
        v.shrink_to_fit();
        check(v.get_size() == 0 && v.get_capacity() == 0, "clear и shrink_to_fit у пустого безопасны");
    }

    // ---- push_back и pop_back ----
    {
        subvector v;
        bool ok = true;
        for (int i = 0; i < 1000; ++i) ok = ok && v.push_back(i * 3);
        check(ok && v.get_size() == 1000, "1000 push_back: все успешны, size 1000");
        check(v.get_capacity() >= v.get_size(), "capacity не меньше size");
        bool same = true;
        for (unsigned int i = 0; i < 1000; ++i) same = same && v.get(i) == (int)i * 3;
        check(same, "элементы сохранились после всех перевыделений");
        check(v.pop_back() == 999 * 3 && v.get_size() == 999, "pop_back вернул последний, size уменьшился");
        unsigned int before = v.get_capacity();
        v.pop_back();
        check(v.get_capacity() == before, "pop_back не меняет capacity");
    }

    // ---- resize ----
    {
        subvector v;
        for (int i = 0; i < 10; ++i) v.push_back(i);
        check(v.resize(100) && v.get_capacity() == 100 && v.get_size() == 10,
              "resize(100): capacity 100, size прежний");
        bool same = true;
        for (unsigned int i = 0; i < 10; ++i) same = same && v.get(i) == (int)i;
        check(same, "resize вверх сохраняет элементы");
        check(v.resize(4) && v.get_capacity() == 4 && v.get_size() == 4, "resize(4): данные обрезаны до 4");
        check(v.get(0) == 0 && v.get(3) == 3, "после обрезки остались первые элементы");
        check(v.push_back(77) && v.get_size() == 5 && v.get(4) == 77, "push_back после обрезки работает");
        check(v.resize(0) && v.get_capacity() == 0 && v.get_size() == 0, "resize(0) освобождает всё");
        check(v.push_back(5) && v.get(0) == 5, "push_back после resize(0) работает");
    }

    // ---- shrink_to_fit и clear ----
    {
        subvector v;
        for (int i = 0; i < 37; ++i) v.push_back(i);
        v.shrink_to_fit();
        check(v.get_capacity() == 37 && v.get_size() == 37, "shrink_to_fit: capacity равна size");
        check(v.get(36) == 36, "shrink_to_fit сохраняет элементы");
        unsigned int before = v.get_capacity();
        v.clear();
        check(v.get_size() == 0 && v.get_capacity() == before, "clear: size 0, capacity прежняя");
        v.shrink_to_fit();
        check(v.get_capacity() == 0, "shrink_to_fit после clear освобождает память");
    }

    // ---- Стратегии роста ----
    {
        subvector a;
        a.set_growth_step(10);
        bool ok = true;
        for (int i = 0; i < 95; ++i) {
            a.push_back(i);
            ok = ok && a.get_capacity() == (a.get_size() + 9) / 10 * 10;   // 10, 20, 30, ...
        }
        check(ok, "+10: ёмкость всегда ближайшее кратное 10");

        subvector b;
        b.set_growth_step(100);
        for (int i = 0; i < 101; ++i) b.push_back(i);
        check(b.get_capacity() == 200, "+100: после 101 элемента ёмкость 200");

        subvector c;
        c.set_growth_factor(2.0);
        ok = true;
        for (int i = 0; i < 1000; ++i) {
            c.push_back(i);
            unsigned int cap = c.get_capacity();
            ok = ok && (cap & (cap - 1)) == 0;   // степень двойки
        }
        check(ok && c.get_capacity() == 1024, "x2: ёмкости 1, 2, 4, ..., 1024");

        subvector d;
        d.set_growth_factor(1.5);
        unsigned int expected[] = {1, 2, 3, 4, 6, 9, 13, 19, 28, 42};
        ok = true;
        for (int k = 0; k < 10; ++k) {
            while (d.get_capacity() < expected[k]) d.push_back(0);
            ok = ok && d.get_capacity() == expected[k];
        }
        check(ok, "x1.5: ёмкости 1, 2, 3, 4, 6, 9, 13, 19, 28, 42");
    }

    // ---- Сравнение со std::vector на случайной последовательности операций ----
    {
        subvector v;
        std::vector<int> reference;
        unsigned int state = 2026;
        bool same = true;
        for (int step = 0; step < 200000 && same; ++step) {
            unsigned int r = next_random(state) % 100;
            if (r < 60) {
                int value = (int)(next_random(state) % 1000);
                v.push_back(value);
                reference.push_back(value);
            } else if (r < 95) {
                int expected = 0;
                if (!reference.empty()) {
                    expected = reference.back();
                    reference.pop_back();
                }
                same = same && v.pop_back() == expected;
            } else if (r < 97) {
                v.shrink_to_fit();
            } else if (r < 99) {
                unsigned int cap = next_random(state) % 2000;
                v.resize(cap);
                if (reference.size() > cap) reference.resize(cap);
            } else {
                v.clear();
                reference.clear();
            }
            same = same && v.get_size() == reference.size() && v.get_capacity() >= v.get_size();
            if (same && v.get_size() > 0) {
                same = v.get(v.get_size() - 1) == reference.back() && v.get(0) == reference.front();
            }
        }
        check(same, "200 000 случайных операций: поведение совпало со std::vector");
        bool all = v.get_size() == reference.size();
        for (unsigned int i = 0; all && i < v.get_size(); ++i) all = v.get(i) == reference[i];
        check(all, "итоговое содержимое совпало со std::vector");
    }

    std::cout << (failed == 0 ? "Все проверки пройдены" : "ЕСТЬ ОШИБКИ") << '\n';
    return failed == 0 ? 0 : 1;
}
