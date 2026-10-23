#!/usr/bin/env bash
# Контрольные опыты к отчёту. Результаты — data/control_*.txt.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build data
F="-std=c++17 -O2 -Wall -Wextra"
J="-Wa,-mbranches-within-32B-boundaries"

g++ $F control_order.cpp -o build/control_order
{ ./build/control_order; ./build/control_order warm; } > data/control_order.txt

g++ $F control_malloc.cpp -o build/control_malloc
./build/control_malloc > data/control_malloc.txt

g++ $F control_copy.cpp -o build/control_copy
./build/control_copy > data/control_copy.txt

g++ $F control_std_vs_sub.cpp -o build/control_plain
g++ $F $J control_std_vs_sub.cpp -o build/control_jcc
{
  echo "1. Обычная сборка (-O2)"; ./build/control_plain
  echo; echo "2. С $J (защита от ошибки JCC)"; ./build/control_jcc
  echo; echo "3. То же + glibc без rep movsb (GLIBC_TUNABLES=glibc.cpu.x86_rep_movsb_threshold=0x40000000)"
  GLIBC_TUNABLES=glibc.cpu.x86_rep_movsb_threshold=0x40000000 ./build/control_jcc
  echo; echo "4. То же + без некэширующих записей (… :glibc.cpu.x86_non_temporal_threshold=0x40000000)"
  GLIBC_TUNABLES=glibc.cpu.x86_rep_movsb_threshold=0x40000000:glibc.cpu.x86_non_temporal_threshold=0x40000000 ./build/control_jcc
  echo; echo "Пороги glibc на этой машине:"
  /lib64/ld-linux-x86-64.so.2 --list-tunables 2>/dev/null | grep -E "rep_movsb_threshold|non_temporal_threshold|shared_cache_size" || true
} > data/control_std_vs_sub.txt
cat data/control_std_vs_sub.txt
