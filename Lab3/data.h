#ifndef DATA_H
#define DATA_H

#include <cstddef>

#include "text.h"

// Начальное значение генератора. Одинаковый SEED даёт одинаковые входные строки.
const unsigned int SEED = 2026;

// Сколько разных входов готовим для каждой длины.
const std::size_t SAMPLES = 8;

// Следующее псевдослучайное число (линейный конгруэнтный генератор).
unsigned int next_random(unsigned int& state);

// Записать size символов: печатные ASCII, пробелы и табуляции. Терминатор не пишет.
void fill_text(char* out, std::size_t size, unsigned int& state);

// Новый массив из size символов и '\0'. Владелец - вызывающий код (delete[]).
char* make_text(std::size_t size, unsigned int& state);

// Заполнить все байты блока; последний байт - '\0'.
void fill_block(Block& block, unsigned int& state);

#endif
