#!/bin/bash
# Полный прогон решения Claude: тесты -> замеры -> сравнение реализаций -> графики -> PDF.
# Около 15 минут; почти всё время уходит на стратегии +10 и +100 с честным копированием.
set -e
cd "$(dirname "$0")"
mkdir -p build data plots
F="-std=c++17 -Wall -Wextra"

g++ $F -O1 -g -fsanitize=address,undefined,float-cast-overflow tests.cpp -o build/tests && ./build/tests

g++ $F -O2 bench.cpp -o build/bench
for p in capacity latency realloc step factor types strategies; do ./build/bench $p data; done

# последовательность ёмкостей у двух стандартных библиотек
g++ $F -O2 capseq.cpp -o build/capseq_gcc && ./build/capseq_gcc > data/capacity_libstdcxx.csv
if clang++ -stdlib=libc++ $F -O2 capseq.cpp -o build/capseq_libcxx 2>/dev/null; then
    ./build/capseq_libcxx > data/capacity_libcxx.csv
fi

python3 compare.py
python3 plot.py
python3 make_pdf.py
