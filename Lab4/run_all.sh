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
$CXX -std=c++17 -O2 -Wall -Wextra bench.cpp -o build/bench
./build/bench all data "$@"

echo "== графики =="
python3 plot.py
