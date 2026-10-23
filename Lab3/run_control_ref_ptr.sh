#!/usr/bin/env bash
# Контрольный опыт ref/ptr в двух сборках: обычной и с выравниванием переходов (ошибка JCC).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
for n in 16 1024 16384; do
  for mode in plain jcc; do
    extra=""; [ "$mode" = jcc ] && extra="-Wa,-mbranches-within-32B-boundaries"
    g++ -std=c++17 -O2 $extra -DBLOCK_SIZE=$n control_ref_ptr.cpp text.cpp inputs.cpp -o build/control_ref_ptr_$mode
    echo "== BLOCK_SIZE=$n, сборка: $mode ${extra}"
    ./build/control_ref_ptr_$mode
  done
done
