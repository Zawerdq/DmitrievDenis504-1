#ifndef TEXT_H
#define TEXT_H

#include <cstddef>

// Размер массива внутри Block. Чтобы исследовать другой размер,
// поменяйте число и пересоберите проект (run.sh делает это ключом -DBLOCK_SIZE=...).
#ifndef BLOCK_SIZE
#define BLOCK_SIZE 1024
#endif

// Символы лежат внутри самого объекта.
// Последний байт - '\0', полезная длина равна BLOCK_SIZE - 1.
struct Block {
    char data[BLOCK_SIZE];
};

// Описатель чужого текста: адрес и длина. Памятью не владеет и ничего не освобождает.
// При size > 0 по адресу data должно быть не меньше size живых символов.
struct Text {
    const char* data;
    std::size_t size;
};

// Результат полного прохода: число слов и сумма кодов байтов.
struct Stats {
    std::size_t words = 0;
    unsigned long long checksum = 0;
};

// ---- Маленький скалярный объект: вернуть значение плюс один ----
unsigned int scalar_value(unsigned int x);
unsigned int scalar_ref(const unsigned int& x);
unsigned int scalar_ptr(const unsigned int* x);

// ---- Общая работа над текстом ----
unsigned char first(Text text);   // код первого байта, для пустого текста 0
Stats analyze(Text text);         // слова и сумма кодов за один проход

// ---- Block: короткая работа ----
unsigned char block_first_value(Block text);
unsigned char block_first_ref(const Block& text);
unsigned char block_first_ptr(const Block* text);   // text != nullptr

// ---- Block: полный проход ----
Stats block_full_value(Block text);
Stats block_full_ref(const Block& text);
Stats block_full_ptr(const Block* text);            // text != nullptr

// ---- Text: короткая работа ----
unsigned char text_first_value(Text text);
unsigned char text_first_ref(const Text& text);
unsigned char text_first_ptr(const Text* text);     // text != nullptr

// ---- Text: полный проход ----
Stats text_full_value(Text text);
Stats text_full_ref(const Text& text);
Stats text_full_ptr(const Text* text);              // text != nullptr

// Независимая копия: new char[size + 1], в конце '\0'.
// Владелец результата - вызывающий код, он один раз делает delete[].
char* clone_text(Text text);

#endif
