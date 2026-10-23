// control_branches.cpp — контрольный опыт к отчёту: почему полный проход стоит 2–3 нс на байт
// и почему в опыте B время на анализ падало с ростом K.
//
// Гипотеза: проход ограничен неверно предсказанными переходами на случайных пробелах.
// Если так, то
//   (1) на тексте без разделителей (переходы предсказуемы) проход станет в разы быстрее;
//   (2) вариант без ветвлений на том же случайном тексте тоже станет быстрее;
//   (3) повторный анализ ОДНОЙ и той же строки быстрее, чем анализ разных строк по кругу, —
//       но только пока строка короткая настолько, что предсказатель успевает её «запомнить»;
//   (4) у варианта без ветвлений разница между «одна строка» и «разные строки» исчезает.
//
//   g++ -std=c++17 -O2 control_branches.cpp text.cpp inputs.cpp -o control_branches && ./control_branches
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <string>
#include <vector>

#include "inputs.h"
#include "text.h"

// Тот же результат, что text_full_ref, но без условных переходов внутри цикла.
__attribute__((noinline)) Stats full_branchless(const Text& t) {
    Stats s{0, 0};
    unsigned prev_sep = 1;
    for (std::size_t i = 0; i < t.size; ++i) {
        unsigned char c = static_cast<unsigned char>(t.data[i]);
        unsigned sep = (c == ' ') | (c == '\t');
        s.words += (prev_sep & (sep ^ 1u));
        s.sum += c;
        prev_sep = sep;
    }
    return s;
}

using Fn = Stats (*)(const Text&);

// Время на байт: серия вызовов fn, вход меняется по кругу из texts (или всегда texts[0]).
static double ns_per_byte(Fn fn, const std::vector<Text>& texts, bool same, std::size_t L) {
    const std::size_t mask = texts.size() - 1;
    std::size_t calls = std::max<std::size_t>(64, static_cast<std::size_t>(4e8 / (L * 3)));  // ~0.1–0.3 с на серию
    double best = 1e18;
    unsigned long long acc = 0;
    for (int trial = 0; trial < 9; ++trial) {
        auto t0 = std::chrono::steady_clock::now();
        for (std::size_t g = 0; g < calls; ++g) {
            Stats s = fn(texts[same ? 0 : (g & mask)]);
            acc += s.words + s.sum;
        }
        double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        best = std::min(best, sec);
    }
    if (acc == 42) std::puts("");  // использовать результат
    return best / calls / L * 1e9;
}

static Stats ref_adapter(const Text& t) { return text_full_ref(t); }

int main() {
    std::printf("нс на байт (минимум из 9 серий)\n");
    std::printf("%7s | %-22s | %13s | %13s\n", "L", "текст", "с ветвлениями", "без ветвлений");
    for (std::size_t L : {15ul, 1023ul, 16383ul}) {
        auto rnd = generate_strings(8, L, DEFAULT_SEED);
        std::vector<std::string> plain(8, std::string(L, 'a'));  // ни одного разделителя
        for (int k = 0; k < 8; ++k) plain[k][0] = static_cast<char>('a' + k);
        std::vector<Text> tr, tp;
        for (auto& s : rnd) tr.push_back(Text{s.data(), s.size()});
        for (auto& s : plain) tp.push_back(Text{s.data(), s.size()});
        // проверка: оба прохода дают одинаковый результат
        for (auto& t : tr)
            if (!(full_branchless(t) == text_full_ref(t))) { std::puts("MISMATCH"); return 1; }

        double r_many = ns_per_byte(ref_adapter, tr, false, L);
        double r_same = ns_per_byte(ref_adapter, tr, true, L);
        double b_many = ns_per_byte(full_branchless, tr, false, L);
        double b_same = ns_per_byte(full_branchless, tr, true, L);
        double p_many = ns_per_byte(ref_adapter, tp, false, L);
        std::printf("%7zu | случайный, 8 строк     | %13.3f | %13.3f\n", L, r_many, b_many);
        std::printf("%7zu | случайный, одна строка | %13.3f | %13.3f\n", L, r_same, b_same);
        std::printf("%7zu | без разделителей       | %13.3f | %13s\n", L, p_many, "—");
    }
    return 0;
}
