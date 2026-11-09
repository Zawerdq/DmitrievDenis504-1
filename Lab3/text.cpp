#include "text.h"

// ---------------- Скаляр ----------------

unsigned int scalar_value(unsigned int x) {
    return x + 1;
}

unsigned int scalar_ref(const unsigned int& x) {
    return x + 1;
}

unsigned int scalar_ptr(const unsigned int* x) {
    return *x + 1;
}

// ---------------- Общая работа ----------------

unsigned char first(Text text) {
    return text.size == 0 ? 0 : (unsigned char)text.data[0];
}

// Слово - непустая последовательность между пробелами и табуляциями.
// Пунктуация входит в слово. Сумма считается по кодам unsigned char.
Stats analyze(Text text) {
    Stats result;
    bool inside_word = false;
    for (std::size_t i = 0; i < text.size; ++i) {
        char c = text.data[i];
        result.checksum += (unsigned char)c;
        if (c == ' ' || c == '\t') {
            inside_word = false;
        } else if (!inside_word) {
            ++result.words;
            inside_word = true;
        }
    }
    return result;
}

// ---------------- Block ----------------
// Полезная длина блока на единицу меньше массива: последний байт занят '\0'.

unsigned char block_first_value(Block text) {
    return (unsigned char)text.data[0];
}

unsigned char block_first_ref(const Block& text) {
    return (unsigned char)text.data[0];
}

unsigned char block_first_ptr(const Block* text) {
    return (unsigned char)text->data[0];
}

Stats block_full_value(Block text) {
    return analyze({text.data, sizeof(text.data) - 1});
}

Stats block_full_ref(const Block& text) {
    return analyze({text.data, sizeof(text.data) - 1});
}

Stats block_full_ptr(const Block* text) {
    return analyze({text->data, sizeof(text->data) - 1});
}

// ---------------- Text ----------------
// Во всех трёх вариантах символы остаются общими: копируется только описатель.

unsigned char text_first_value(Text text) {
    return first(text);
}

unsigned char text_first_ref(const Text& text) {
    return first(text);
}

unsigned char text_first_ptr(const Text* text) {
    return first(*text);
}

Stats text_full_value(Text text) {
    return analyze(text);
}

Stats text_full_ref(const Text& text) {
    return analyze(text);
}

Stats text_full_ptr(const Text* text) {
    return analyze(*text);
}

// ---------------- Независимая копия ----------------

char* clone_text(Text text) {
    char* copy = new char[text.size + 1];
    for (std::size_t i = 0; i < text.size; ++i) {
        copy[i] = text.data[i];
    }
    copy[text.size] = '\0';
    return copy;
}
