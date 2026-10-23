#!/usr/bin/env bash
# Полный воспроизводимый прогон: сборка, проверки, опыты A и B, графики.
# Использование: ./run_experiments.sh [доп. опции research; по умолчанию --trials 9 --target-ms 80]
set -euo pipefail
if [ $# -eq 0 ]; then set -- --trials 9 --target-ms 80; fi
cd "$(dirname "$0")"

CXX=${CXX:-g++}
STD="-std=c++17 -Wall -Wextra"
SIZES="16 1024 16384"
mkdir -p build data plots

echo "== проверки корректности =="
for n in $SIZES; do
  $CXX $STD -O0 -DBLOCK_SIZE=$n tests.cpp text.cpp inputs.cpp -o build/tests_$n
  ./build/tests_$n
done

echo "== сборка исследования (без LTO; объявления в text.h, определения в text.cpp) =="
for n in $SIZES; do
  $CXX $STD -O0 -DBLOCK_SIZE=$n main.cpp text.cpp inputs.cpp -o build/research_debug_$n
  $CXX $STD -O2 -DBLOCK_SIZE=$n main.cpp text.cpp inputs.cpp -o build/research_opt_$n
done

echo "== опыт A =="
for n in $SIZES; do
  extra=""; [ "$n" = "1024" ] && extra="--scalar"
  ./build/research_debug_$n A O0 data $extra "$@"
  ./build/research_opt_$n   A O2 data $extra "$@"
done

echo "== опыт B (только -O2) =="
./build/research_opt_1024 B O2 data "$@"

echo "== графики =="
python3 plot.py
