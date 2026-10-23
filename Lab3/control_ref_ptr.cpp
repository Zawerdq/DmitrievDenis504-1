// control_ref_ptr.cpp — контрольный опыт: откуда берутся невоспроизводимые 10–20 % между
// text_full_ref и text_full_ptr, если их машинный код идентичен (см. asm_check.sh).
//
// Гипотеза: процессор этой машины (Intel, модель 85: Skylake-SP / Cascade Lake) подвержен ошибке JCC —
// условный переход, пересекающий 32-байтную границу или заканчивающийся на ней, не кэшируется в DSB,
// и цикл с таким переходом исполняется медленнее. Две одинаковые функции лежат по разным адресам,
// поэтому одна может попасть под эффект, а другая нет.
//
// Проверка: собрать дважды — обычным g++ -O2 и с -Wa,-mbranches-within-32B-boundaries (ассемблер
// сдвигает переходы так, чтобы они не касались 32-байтных границ). Скрипт run_control_ref_ptr.sh.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <vector>

#include "inputs.h"
#include "text.h"

template <class F>
static double ns_per_byte(F f, const Text& t, std::size_t calls) {
    unsigned long long acc = 0;
    auto t0 = std::chrono::steady_clock::now();
    for (std::size_t i = 0; i < calls; ++i) {
        Stats s = f(t);
        acc += s.words + s.sum;
    }
    double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    if (acc == 42) std::puts("");
    return sec / calls / t.size * 1e9;
}

int main() {
    // Текст без разделителей: переходы предсказуемы, поэтому видна именно цена размещения кода,
    // а не неверных предсказаний (они дали бы шум того же порядка).
    std::vector<std::string> s = generate_strings(1, 4096, DEFAULT_SEED);
    for (char& c : s[0]) if (c == ' ' || c == '\t') c = 'x';
    Text t{s[0].data(), s[0].size()};
    const std::size_t calls = 20000;
    std::vector<double> r, p;
    for (int trial = 0; trial < 15; ++trial) {  // чередуем, чтобы дрейф машины действовал на обе одинаково
        r.push_back(ns_per_byte([](const Text& x) { return text_full_ref(x); }, t, calls));
        p.push_back(ns_per_byte([](const Text& x) { return text_full_ptr(&x); }, t, calls));
    }
    std::sort(r.begin(), r.end());
    std::sort(p.begin(), p.end());
    auto addr = [](const void* f) { return static_cast<unsigned>(reinterpret_cast<std::uintptr_t>(f) % 64); };
    std::printf("text_full_ref: медиана %.3f нс/байт (адрес mod 64 = %2u)\n", r[7],
                addr(reinterpret_cast<const void*>(&text_full_ref)));
    std::printf("text_full_ptr: медиана %.3f нс/байт (адрес mod 64 = %2u)\n", p[7],
                addr(reinterpret_cast<const void*>(&text_full_ptr)));
    std::printf("ptr / ref = %.3f\n", p[7] / r[7]);
    return 0;
}
