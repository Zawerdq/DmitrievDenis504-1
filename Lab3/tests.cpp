// tests.cpp — проверки корректности до любых измерений.
// Сборка: g++ -O0 -std=c++17 -Wall -Wextra tests.cpp text.cpp inputs.cpp -o tests
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "inputs.h"
#include "text.h"

static int failures = 0;
static int checks = 0;

#define CHECK(cond)                                                           \
    do {                                                                      \
        ++checks;                                                             \
        if (!(cond)) {                                                        \
            ++failures;                                                       \
            std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond);       \
        }                                                                     \
    } while (0)

static Text text_of(const std::string& s) { return Text{s.empty() ? nullptr : s.data(), s.size()}; }

// Все три способа передачи Text и обработка копии дают один и тот же результат.
static void check_text_case(const std::string& s, unsigned long long words, unsigned long long sum,
                            unsigned char first) {
    const std::string before = s;
    Text t = text_of(s);
    Stats expected{words, sum};
    CHECK(text_full_val(t) == expected);
    CHECK(text_full_ref(t) == expected);
    CHECK(text_full_ptr(&t) == expected);
    CHECK(text_first_val(t) == first);
    CHECK(text_first_ref(t) == first);
    CHECK(text_first_ptr(&t) == first);

    char* copy = clone_text(t);  // владелец копии — этот блок кода
    CHECK(copy != nullptr);
    CHECK(copy[s.size()] == '\0');
    CHECK(std::memcmp(copy, s.data(), s.size()) == 0);
    Text ct{copy, s.size()};
    CHECK(text_full_val(ct) == expected);
    CHECK(text_first_ref(ct) == first);
    delete[] copy;  // ровно один раз

    CHECK(s == before);  // обработчики только читают
}

static unsigned long long naive_sum(const std::string& s) {
    unsigned long long r = 0;
    for (char c : s) r += static_cast<unsigned char>(c);
    return r;
}

static unsigned long long naive_words(const std::string& s) {
    unsigned long long w = 0;
    bool in = false;
    for (char c : s) {
        bool sep = (c == ' ' || c == '\t');
        if (!sep && !in) ++w;
        in = !sep;
    }
    return w;
}

int main() {
    // --- пустой текст ---
    {
        Text empty{nullptr, 0};
        CHECK(text_full_val(empty) == (Stats{0, 0}));
        CHECK(text_first_val(empty) == 0);
        char* c = clone_text(empty);  // выделяется один элемент под '\0'
        CHECK(c[0] == '\0');
        delete[] c;
        check_text_case("", 0, 0, 0);
    }
    // --- пример из задания ---
    check_text_case("one two", 2, 700, 'o');
    // --- один символ ---
    check_text_case("a", 1, 97, 'a');
    check_text_case(" ", 0, 32, ' ');
    // --- только разделители ---
    check_text_case(" \t  \t", 0, 32 * 3 + 9 * 2, ' ');
    // --- несколько слов, пунктуация входит в слово, табуляции ---
    check_text_case("Hello, world!\tfoo  bar", 4, naive_sum("Hello, world!\tfoo  bar"), 'H');
    check_text_case("\tlead and trail ", 3, naive_sum("\tlead and trail "), '\t');
    check_text_case("~!@#", 1, naive_sum("~!@#"), '~');

    // --- длинная строка 100 000 символов ---
    {
        auto v = generate_strings(1, 100000, DEFAULT_SEED);
        const std::string& s = v[0];
        check_text_case(s, naive_words(s), naive_sum(s), static_cast<unsigned char>(s[0]));
    }

    // --- генератор: детерминированность, нет '\0', только печатные/таб ---
    {
        auto a = generate_strings(4, 300, 123);
        auto b = generate_strings(4, 300, 123);
        CHECK(a == b);
        CHECK(a[0] != a[1]);
        bool ok = true;
        for (auto& s : a)
            for (char c : s) {
                unsigned char u = static_cast<unsigned char>(c);
                if (!(u == '\t' || (u >= 32 && u <= 126))) ok = false;
            }
        CHECK(ok);
    }

    // --- Block: все способы передачи совпадают с Text-описателем того же текста ---
    {
        auto v = generate_strings(3, block_length(), 7);
        for (auto& s : v) {
            Block b;
            fill_block(b, s);
            CHECK(b.data[block_length()] == '\0');
            CHECK(std::strlen(b.data) == block_length());
            Stats exp{naive_words(s), naive_sum(s)};
            CHECK(block_full_val(b) == exp);
            CHECK(block_full_ref(b) == exp);
            CHECK(block_full_ptr(&b) == exp);
            CHECK(text_full_val(as_text(b)) == exp);
            unsigned char f = static_cast<unsigned char>(s[0]);
            CHECK(block_first_val(b) == f);
            CHECK(block_first_ref(b) == f);
            CHECK(block_first_ptr(&b) == f);
            Block before = b;
            (void)block_full_val(b);
            (void)block_full_ref(b);
            CHECK(std::memcmp(before.data, b.data, BLOCK_SIZE) == 0);  // не изменён
        }
    }

    // --- скаляр ---
    {
        unsigned int x = 41;
        CHECK(scalar_val(x) == 42);
        CHECK(scalar_ref(x) == 42);
        CHECK(scalar_ptr(&x) == 42);
        CHECK(x == 41);
    }

    // --- независимость копии ---
    {
        // Владелец исходного текста — массив src (изменяемый, на стеке).
        char src[] = "alpha beta";
        Text view{src, sizeof(src) - 1};   // описатель указывает на src
        char* copy = clone_text(view);     // независимая копия, владелец — этот блок
        src[0] = 'A';                      // меняем источник
        CHECK(view.data[0] == 'A');        // описатель видит изменение
        CHECK(copy[0] == 'a');             // копия хранит прежние символы
        CHECK(std::strcmp(copy, "alpha beta") == 0);
        CHECK(text_full_val(view) == (Stats{2, naive_sum("Alpha beta")}));
        CHECK(text_full_val(Text{copy, 10}) == (Stats{2, naive_sum("alpha beta")}));
        delete[] copy;
        // view живёт не дольше src: src уничтожается в конце блока, view — тоже.
    }

    // --- Text по значению копирует описатель, а не символы ---
    {
        std::string s = "same address";
        Text a = text_of(s);
        Text b = a;  // копия описателя
        CHECK(a.data == b.data);
        CHECK(sizeof(Text) == sizeof(const char*) + sizeof(std::size_t));
    }

    // --- чтение файла: LF и CRLF не входят в текст ---
    {
        const char* path = "tests_tmp_lines.txt";
        std::FILE* f = std::fopen(path, "wb");
        std::fputs("one two\r\n\tx\n\nlast", f);
        std::fclose(f);
        std::vector<std::string> lines;
        CHECK(read_lines(path, lines));
        CHECK(lines.size() == 4);
        if (lines.size() == 4) {
            CHECK(lines[0] == "one two");
            CHECK(lines[1] == "\tx");
            CHECK(lines[2].empty());
            CHECK(lines[3] == "last");
        }
        std::remove(path);
    }

    std::printf("BLOCK_SIZE=%d: %d checks, %d failures\n", BLOCK_SIZE, checks, failures);
    return failures == 0 ? 0 : 1;
}
