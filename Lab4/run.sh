#!/bin/bash
# Полный прогон: проверки -> сборка -> опыты -> графики. Занимает около 6 минут:
# почти всё время уходит на медленные стратегии +10 и +100.
set -e
cd "$(dirname "$0")"
mkdir -p build data plots

FLAGS="-std=c++17 -Wall -Wextra"

g++ $FLAGS -O0 tests.cpp subvector.cpp -o build/tests
./build/tests | tail -1

g++ $FLAGS -O2 main.cpp subvector.cpp -o build/bench
./build/bench

python3 plot.py
