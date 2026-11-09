// Проверки корректности. Запускаются до измерений:
//   g++ -O0 tests.cpp text.cpp data.cpp -o tests && ./tests
#include <cstddef>
#include <iostream>

#include "data.h"
#include "text.h"

int failed = 0;

void check(bool ok, const char* name) {
    std::cout << (ok ? "[ OK ] " : "[FAIL] ") << name << '\n';
    if (!ok) ++failed;
}

// Длина C-строки без терминатора.
std::size_t length(const char* s) {
    std::size_t n = 0;
    while (s[n] != '\0') ++n;
    return n;
}

bool same(Stats a, Stats b) {
    return a.words == b.words && a.checksum == b.checksum;
}

// Ожидаемые слова и сумма для строки-литерала.
bool expect(const char* s, std::size_t words, unsigned long long checksum) {
    Stats r = analyze({s, length(s)});
    return r.words == words && r.checksum == checksum;
}

bool equal_chars(const char* a, const char* b, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i) {
        if (a[i] != b[i]) return false;
    }
    return true;
}

int main() {
    // ---- Анализатор на простых входах ----
    check(expect("", 0, 0), "пустой текст: 0 слов, сумма 0");
    check(same(analyze({nullptr, 0}), Stats{}), "nullptr при нулевой длине");
    check(expect("a", 1, 97), "один символ");
    check(expect(" \t  \t", 0, 32 * 3 + 9 * 2), "только разделители: 0 слов");
    check(expect("one two", 2, 700), "\"one two\": 2 слова, сумма 700");
    check(expect("  one\ttwo  three, four!  ", 4, 1958),
          "несколько слов, табуляция, пунктуация внутри слова");
    check(expect("\tx\t\ty\t", 2, 120 + 121 + 9 * 4), "слова между табуляциями");

    // ---- Короткий обработчик ----
    check(first({"", 0}) == 0, "first: пустой текст даёт 0");
    check(first({nullptr, 0}) == 0, "first: nullptr при нулевой длине даёт 0");
    check(first({"one", 3}) == 'o', "first: код первого байта");
    char high[] = {(char)200, 'a', '\0'};
    check(first({high, 2}) == 200, "first: байт 200 читается как unsigned char");
    check(analyze({high, 2}).checksum == 297, "сумма считает байт 200 как 200, а не как -56");

    // ---- Одинаковые результаты при разных способах передачи ----
    unsigned int state = SEED;

    unsigned int x = 41;
    check(scalar_value(x) == 42 && scalar_ref(x) == 42 && scalar_ptr(&x) == 42,
          "скаляр: value, ref, ptr дают x + 1");

    Block* block = new Block;           // блок может быть большим, держим в динамической памяти
    fill_block(*block, state);
    Block* untouched = new Block(*block);
    Stats direct = analyze({block->data, sizeof(block->data) - 1});
    check(same(block_full_value(*block), direct) && same(block_full_ref(*block), direct) &&
              same(block_full_ptr(block), direct),
          "Block: полный проход одинаков для value, ref, ptr");
    unsigned char b0 = (unsigned char)block->data[0];
    check(block_first_value(*block) == b0 && block_first_ref(*block) == b0 &&
              block_first_ptr(block) == b0,
          "Block: первый байт одинаков для value, ref, ptr");
    check(equal_chars(block->data, untouched->data, sizeof(block->data)),
          "Block: обработчики не изменили исходные данные");
    check(block->data[sizeof(block->data) - 1] == '\0', "Block: последний байт - терминатор");

    std::size_t n = BLOCK_SIZE - 1;
    char* source = make_text(n, state);
    char* backup = clone_text({source, n});
    Text t{source, n};
    Stats ts = analyze(t);
    check(same(text_full_value(t), ts) && same(text_full_ref(t), ts) && same(text_full_ptr(&t), ts),
          "Text: полный проход одинаков для value, ref, ptr");
    check(text_first_value(t) == first(t) && text_first_ref(t) == first(t) &&
              text_first_ptr(&t) == first(t),
          "Text: первый байт одинаков для value, ref, ptr");
    Text empty{nullptr, 0};
    check(text_first_value(empty) == 0 && text_first_ref(empty) == 0 && text_first_ptr(&empty) == 0,
          "Text: пустой текст во всех трёх вариантах даёт 0");
    check(equal_chars(source, backup, n + 1), "Text: обработчики не изменили исходные данные");
    delete[] backup;
    delete[] source;

    // ---- sizeof(Text) не зависит от длины текста ----
    Text short_text{"abc", 3};
    Text long_text{"abcdefghijklmnopqrstuvwxyz", 26};
    check(sizeof(short_text) == sizeof(long_text) && sizeof(Text) == sizeof(char*) + sizeof(std::size_t),
          "sizeof(Text) = указатель + длина, от текста не зависит");
    check(sizeof(Block) == BLOCK_SIZE, "sizeof(Block) равен размеру массива");

    // ---- clone_text ----
    char* empty_copy = clone_text({nullptr, 0});
    check(empty_copy[0] == '\0', "clone_text: у пустого текста один байт с терминатором");
    delete[] empty_copy;

    char word[] = "one two";
    char* copy = clone_text({word, sizeof(word) - 1});
    check(copy != word && equal_chars(copy, word, sizeof(word)),
          "clone_text: другой адрес, те же символы и терминатор");
    check(same(analyze({copy, sizeof(word) - 1}), analyze({word, sizeof(word) - 1})),
          "анализ копии совпадает с анализом исходного текста");
    delete[] copy;

    // ---- Длинная строка: 100 000 символов ----
    const std::size_t LONG = 100000;
    char* big = make_text(LONG, state);
    // Независимый подсчёт "в лоб", чтобы было с чем сравнить.
    std::size_t words = 0;
    unsigned long long sum = 0;
    for (std::size_t i = 0; i < LONG; ++i) {
        sum += (unsigned char)big[i];
        bool sep = big[i] == ' ' || big[i] == '\t';
        bool prev_sep = i == 0 || big[i - 1] == ' ' || big[i - 1] == '\t';
        if (!sep && prev_sep) ++words;
    }
    Stats big_stats = analyze({big, LONG});
    check(big_stats.words == words && big_stats.checksum == sum,
          "100 000 символов: анализатор совпал с независимым подсчётом");
    char* big_copy = clone_text({big, LONG});
    check(equal_chars(big, big_copy, LONG) && big_copy[LONG] == '\0',
          "100 000 символов: копия совпадает, терминатор на месте");
    check(same(analyze({big_copy, LONG}), big_stats), "100 000 символов: анализ копии тот же");
    delete[] big_copy;
    delete[] big;

    // ---- Независимость копии (отдельный опыт, не замер) ----
    // Владелец исходного текста - массив original в этой функции.
    char original[] = "one two";
    Text borrowed{original, sizeof(original) - 1};
    Text descriptor_copy = borrowed;          // копия описателя: тот же адрес
    char* owned_copy = clone_text(borrowed);  // независимые символы
    original[0] = 'O';
    check(first(borrowed) == 'O' && first(descriptor_copy) == 'O',
          "после изменения источника оба описателя видят 'O'");
    check(descriptor_copy.data == borrowed.data, "копия Text хранит тот же адрес");
    check(owned_copy[0] == 'o', "независимая копия сохранила прежнее 'o'");
    check(analyze({owned_copy, borrowed.size}).checksum == 700 && analyze(borrowed).checksum == 668,
          "сумма копии 700, сумма изменённого источника 668");
    delete[] owned_copy;                      // копия освобождена ровно один раз

    delete untouched;
    delete block;

    std::cout << (failed == 0 ? "Все проверки пройдены" : "ЕСТЬ ОШИБКИ") << '\n';
    return failed == 0 ? 0 : 1;
}
