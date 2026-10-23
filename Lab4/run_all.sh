#!/usr/bin/env bash
# Полный прогон: тесты, сборка, все замеры, графики.
set -euo pipefail
cd "$(dirname "$0")"
CXX=${CXX:-g++}
mkdir -p build data plots

echo "== тесты =="
$CXX -std=c++17 -O0 -Wall -Wextra tests.cpp -o build/tests
./build/tests

echo "== замеры =="
# -mbranches-within-32B-boundaries — защита от ошибки JCC (см. отчёт, раздел 2)
$CXX -std=c++17 -O2 -Wall -Wextra -Wa,-mbranches-within-32B-boundaries bench.cpp -o build/bench
./build/bench all data "$@"

echo "== графики =="
python3 plot.py
