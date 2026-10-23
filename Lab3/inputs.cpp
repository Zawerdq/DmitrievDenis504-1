// inputs.cpp — генерация и чтение входных строк.
#include "inputs.h"

#include <fstream>
#include <random>

std::vector<std::string> generate_strings(std::size_t count, std::size_t length, std::uint32_t seed) {
    // Отдельный поток генератора на каждую длину, чтобы набор не зависел от порядка вызовов.
    std::mt19937 gen(seed ^ static_cast<std::uint32_t>(length * 2654435761u));
    std::uniform_int_distribution<int> kind(0, 99);
    std::uniform_int_distribution<int> printable(33, 126);  // видимые символы, без пробела
    std::vector<std::string> res;
    res.reserve(count);
    for (std::size_t k = 0; k < count; ++k) {
        std::string s;
        s.resize(length);
        for (std::size_t i = 0; i < length; ++i) {
            int r = kind(gen);
            if (r < 15) s[i] = ' ';          // ~15% пробелов
            else if (r < 18) s[i] = '\t';    // ~3% табуляций
            else s[i] = static_cast<char>(printable(gen));
        }
        res.push_back(std::move(s));
    }
    return res;
}

bool read_lines(const std::string& path, std::vector<std::string>& out) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    std::string line;
    while (std::getline(in, line)) {           // LF — граница записи
        if (!line.empty() && line.back() == '\r') line.pop_back();  // CRLF
        out.push_back(line);
    }
    return true;
}

void fill_block(Block& b, const std::string& src) {
    const std::size_t n = block_length();
    for (std::size_t i = 0; i < n; ++i)
        b.data[i] = src.empty() ? 'x' : src[i % src.size()];
    b.data[n] = '\0';
}
