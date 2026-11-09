#!/bin/bash
# Полный прогон: проверки -> сборки -> опыты -> графики. Занимает несколько минут.
set -e
cd "$(dirname "$0")"
mkdir -p build data plots

FLAGS="-std=c++17 -Wall -Wextra"

# 1. Проверки корректности для каждого размера блока.
for SIZE in 16 1024 16384; do
    g++ $FLAGS -O0 -DBLOCK_SIZE=$SIZE tests.cpp text.cpp data.cpp -o build/tests_$SIZE
    ./build/tests_$SIZE | tail -1
done

# 2. Опыт A: каждый размер блока - отдельная сборка, без оптимизации и с ней.
for SIZE in 16 1024 16384; do
    g++ $FLAGS -O0 -DBLOCK_SIZE=$SIZE main.cpp text.cpp data.cpp -o build/research_debug_$SIZE
    g++ $FLAGS -O2 -DBLOCK_SIZE=$SIZE main.cpp text.cpp data.cpp -o build/research_opt_$SIZE
    ./build/research_debug_$SIZE A O0
    ./build/research_opt_$SIZE A O2
done

# 3. Скаляр (от размера блока не зависит) и опыт B (только оптимизированная сборка).
./build/research_debug_1024 S O0
./build/research_opt_1024 S O2
./build/research_opt_1024 B O2

# 4. Сводные таблицы и графики.
python3 plot.py
