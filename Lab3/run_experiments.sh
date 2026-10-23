#!/usr/bin/env bash
# Полный воспроизводимый прогон: сборка, проверки, опыты A и B, графики.
# Использование: ./run_experiments.sh [доп. опции research; по умолчанию --trials 9 --target-ms 80]
set -euo pipefail
if [ $# -eq 0 ]; then set -- --trials 9 --target-ms 80; fi
cd "$(dirname "$0")"

CXX=${CXX:-g++}
# -mbranches-within-32B-boundaries: ассемблер не даёт переходам касаться 32-байтных границ.
# Без этого на процессорах Intel с ошибкой JCC (Skylake…Cascade Lake) скорость цикла зависит от того,
# куда он случайно лёг в памяти: одинаковые функции различались в 1.7–2.4 раза (control_ref_ptr.cpp).
STD="-std=c++17 -Wall -Wextra -Wa,-mbranches-within-32B-boundaries"
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
