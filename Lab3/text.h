// text.h — структуры данных и объявления исследуемых функций.
#pragma once

#include <cstddef>

// Размер массива внутри Block. Чтобы исследовать другой размер,
// поменяйте число здесь (или передайте -DBLOCK_SIZE=N компилятору) и пересоберите.
#ifndef BLOCK_SIZE
#define BLOCK_SIZE 1024
#endif

// Символы лежат ВНУТРИ объекта. data[BLOCK_SIZE-1] == '\0',
// полезная длина = BLOCK_SIZE - 1.
struct Block { char data[BLOCK_SIZE]; };

// Описатель чужого текста: адрес + длина. Не владеет памятью и не освобождает её.
// При size > 0 по адресу data доступно не меньше size символов; при size == 0 допустим nullptr.
struct Text { const char* data; std::size_t size; };

// Результат полного прохода.
struct Stats {
    unsigned long long words;
    unsigned long long sum;
};

inline bool operator==(const Stats& a, const Stats& b) {
    return a.words == b.words && a.sum == b.sum;
}

// Полезная длина текста в Block.
constexpr std::size_t block_length() { return BLOCK_SIZE - 1; }

// Описатель для текста внутри Block (Block остаётся владельцем символов).
Text as_text(const Block& b);

// ---------- Скаляр (точка отсчёта) ----------
unsigned int scalar_val(unsigned int x);
unsigned int scalar_ref(const unsigned int& x);
unsigned int scalar_ptr(const unsigned int* x);

// ---------- Block: короткий обработчик (первый байт) ----------
unsigned char block_first_val(Block b);
unsigned char block_first_ref(const Block& b);
unsigned char block_first_ptr(const Block* b);

// ---------- Block: полный обработчик (слова + сумма кодов) ----------
Stats block_full_val(Block b);
Stats block_full_ref(const Block& b);
Stats block_full_ptr(const Block* b);

// ---------- Text: короткий обработчик ----------
unsigned char text_first_val(Text t);
unsigned char text_first_ref(const Text& t);
unsigned char text_first_ptr(const Text* t);

// ---------- Text: полный обработчик ----------
Stats text_full_val(Text t);
Stats text_full_ref(const Text& t);
Stats text_full_ptr(const Text* t);

// Независимая копия: new char[size + 1], символы + '\0'.
// Владелец результата — вызывающий код, освобождает ровно один раз через delete[].
char* clone_text(Text text);
