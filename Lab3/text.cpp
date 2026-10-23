// text.cpp — реализации обработчиков и clone_text.
#include "text.h"

#include <cstring>

namespace {

// Общее ядро обработки: одинаковая работа для всех способов передачи.
inline unsigned char first_byte(const char* p, std::size_t n) {
    return n == 0 ? 0 : static_cast<unsigned char>(p[0]);
}

inline bool is_sep(unsigned char c) { return c == ' ' || c == '\t'; }

// Один проход: число слов (слово — непустая последовательность между ' ' и '\t')
// и сумма кодов байтов как unsigned char.
inline Stats full_pass(const char* p, std::size_t n) {
    Stats s{0, 0};
    bool in_word = false;
    for (std::size_t i = 0; i < n; ++i) {
        unsigned char c = static_cast<unsigned char>(p[i]);
        s.sum += c;
        if (is_sep(c)) {
            in_word = false;
        } else if (!in_word) {
            in_word = true;
            ++s.words;
        }
    }
    return s;
}

}  // namespace

Text as_text(const Block& b) { return Text{b.data, block_length()}; }

// ---------- скаляр ----------
unsigned int scalar_val(unsigned int x) { return x + 1; }
unsigned int scalar_ref(const unsigned int& x) { return x + 1; }
unsigned int scalar_ptr(const unsigned int* x) { return *x + 1; }

// ---------- Block ----------
unsigned char block_first_val(Block b) { return first_byte(b.data, block_length()); }
unsigned char block_first_ref(const Block& b) { return first_byte(b.data, block_length()); }
unsigned char block_first_ptr(const Block* b) { return first_byte(b->data, block_length()); }

Stats block_full_val(Block b) { return full_pass(b.data, block_length()); }
Stats block_full_ref(const Block& b) { return full_pass(b.data, block_length()); }
Stats block_full_ptr(const Block* b) { return full_pass(b->data, block_length()); }

// ---------- Text ----------
unsigned char text_first_val(Text t) { return first_byte(t.data, t.size); }
unsigned char text_first_ref(const Text& t) { return first_byte(t.data, t.size); }
unsigned char text_first_ptr(const Text* t) { return first_byte(t->data, t->size); }

Stats text_full_val(Text t) { return full_pass(t.data, t.size); }
Stats text_full_ref(const Text& t) { return full_pass(t.data, t.size); }
Stats text_full_ptr(const Text* t) { return full_pass(t->data, t->size); }

// ---------- копия ----------
char* clone_text(Text text) {
    char* copy = new char[text.size + 1];  // даже для пустого текста — 1 элемент под '\0'
    if (text.size > 0) std::memcpy(copy, text.data, text.size);
    copy[text.size] = '\0';
    return copy;
}
