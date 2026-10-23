// inputs.h — подготовка входных данных (вне таймера).
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "text.h"

// Начальное значение генератора по умолчанию (записано в README).
constexpr std::uint32_t DEFAULT_SEED = 20261023u;

// Генерирует count различных строк длины length из печатных ASCII-символов,
// пробелов и табуляций (без '\0'). Детерминированно для данного seed.
std::vector<std::string> generate_strings(std::size_t count, std::size_t length, std::uint32_t seed);

// Читает непустые и пустые записи из файла: границы — LF или CRLF, сами символы
// перевода строки в текст не входят. Возвращает false, если файл не открылся.
bool read_lines(const std::string& path, std::vector<std::string>& out);

// Заполняет Block символами строки src (берутся первые block_length() символов,
// при нехватке строка повторяется); последний байт — '\0'.
void fill_block(Block& b, const std::string& src);
