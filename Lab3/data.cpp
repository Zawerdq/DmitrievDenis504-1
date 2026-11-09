#include "data.h"

unsigned int next_random(unsigned int& state) {
    state = state * 1664525u + 1013904223u;
    return state >> 8;   // младшие биты у такого генератора слабые, отбрасываем их
}

void fill_text(char* out, std::size_t size, unsigned int& state) {
    for (std::size_t i = 0; i < size; ++i) {
        unsigned int r = next_random(state) % 40;
        if (r < 5) {
            out[i] = ' ';                 // примерно каждый восьмой символ - пробел
        } else if (r == 5) {
            out[i] = '\t';                // иногда табуляция
        } else {
            out[i] = (char)(33 + next_random(state) % 94);   // печатные '!'..'~'
        }
    }
}

char* make_text(std::size_t size, unsigned int& state) {
    char* text = new char[size + 1];
    fill_text(text, size, state);
    text[size] = '\0';
    return text;
}

void fill_block(Block& block, unsigned int& state) {
    fill_text(block.data, sizeof(block.data) - 1, state);
    block.data[sizeof(block.data) - 1] = '\0';
}
