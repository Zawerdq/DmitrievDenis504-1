# Lab4 · subvector — решение Claude

Итоговый отчёт: **[Lab4_subvector_report.pdf](Lab4_subvector_report.pdf)** (исходник — [REPORT.md](REPORT.md)). В нём задание, теория, устройство `std::vector`, все замеры и графики, сравнение с решениями Fable (`../`) и Codex (`../codex/`), реализации из интернета, затраты ИИ и выводы.

| Файл | Что внутри |
|---|---|
| `subvector.h`, `subvector.cpp` | структура `mas / top / capacity` и функции из задания; стратегия роста (+c или ×k) и способ перевыделения (new+цикл, new+memcpy, realloc) |
| `tests.cpp` | 3065 проверок, сборка с ASan/UBSan, сверка со `std::vector` после каждой операции |
| `bench.cpp` | замеры: `capacity latency realloc step factor types strategies` |
| `capseq.cpp` | последовательность ёмкостей `std::vector` (libstdc++ и libc++) |
| `compare.cpp`, `compare.py` | общий стенд для Fable, Codex, Claude и двух `std::vector` |
| `plot.py` | 12 графиков в `plots/` и сводка чисел `data/summary.json` |
| `make_pdf.py`, `report.css` | REPORT.md → HTML (pandoc) → PDF (Chromium) |
| `run.sh` | всё подряд, ≈15 минут |
| `data/` | все исходные CSV |

Главное отличие от двух предыдущих решений: способ переноса вынесен в отдельный параметр. Видно, что «быстрый +10» у Codex получается из-за `realloc` в glibc, а разные абсолютные секунды у Fable — из-за состояния `malloc`, а не из-за кода.
