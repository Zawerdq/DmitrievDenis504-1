#!/usr/bin/env bash
# Дополнительная проверка гипотез по машинному коду (не входит в замеры).
# Сохраняет в asm/ дизассемблированные обработчики и места вызова Block по значению.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p asm build
CXX=${CXX:-g++}
for opt in O0 O2; do
  for n in 16 1024 16384; do
    $CXX -std=c++17 -$opt -DBLOCK_SIZE=$n -c text.cpp -o build/text_${opt}_$n.o
    $CXX -std=c++17 -$opt -DBLOCK_SIZE=$n -c main.cpp -o build/main_${opt}_$n.o
    objdump -d --no-show-raw-insn -C build/text_${opt}_$n.o > asm/text_${opt}_$n.txt
    # 30 инструкций перед каждым вызовом block_first_val / block_full_val: видно, как вызывающий код копирует Block
    objdump -d --no-show-raw-insn -C -r build/main_${opt}_$n.o \
      | grep -B30 -E "R_X86_64_PLT32\s+block_(first|full)_val" > asm/callsite_value_${opt}_$n.txt || true
  done
done
echo "Копирование Block перед вызовом по значению (-O2):"
for n in 16 1024 16384; do
  printf "  BLOCK_SIZE=%-6s rep movs: %s, call memcpy: %s, movdqu/movups: %s\n" "$n" \
    "$(grep -c 'rep movs' asm/callsite_value_O2_$n.txt || true)" \
    "$(grep -c 'memcpy' asm/callsite_value_O2_$n.txt || true)" \
    "$(grep -cE 'movdqu|movups|movdqa|movaps' asm/callsite_value_O2_$n.txt || true)"
done
