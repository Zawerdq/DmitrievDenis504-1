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

echo
echo "Сравнение машинного кода функций по ссылке и по указателю (-O2, без адресов):"
body() {  # $1 — объектный файл, $2 — имя функции (как в objdump -C)
  objdump -d --no-show-raw-insn -C "$1" \
    | awk -v f="<$2>:" '$2 == f || substr($0, index($0, "<")) == f {on=1; next} on && /^$/ {exit} on' \
    | sed -E 's/^ *[0-9a-f]+:[[:space:]]*//; s/[0-9a-f]+ <[^>]+>//'
}
for n in 16 1024 16384; do
  o=build/text_O2_$n.o
  for pair in "block_full_ref(Block const&)|block_full_ptr(Block const*)" \
              "block_first_ref(Block const&)|block_first_ptr(Block const*)" \
              "text_full_ref(Text const&)|text_full_ptr(Text const*)" \
              "text_first_ref(Text const&)|text_first_ptr(Text const*)"; do
    a=${pair%|*}; b=${pair#*|}
    na=$(body "$o" "$a" | wc -l)
    if [ "$na" -gt 0 ] && diff <(body "$o" "$a") <(body "$o" "$b") > /dev/null; then r="идентичны"; else r="РАЗЛИЧАЮТСЯ"; fi
    printf "  BLOCK_SIZE=%-6s %-30s и %-30s %s (%s инструкций)\n" "$n" "$a" "$b" "$r" "$na"
  done
done
