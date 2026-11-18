# Lab4 · subvector — решение Claude

Решение Claude и стенды, на которых построены оба документа:

* отчёт по лабе — [../../Lab4_subvector.pdf](../../Lab4_subvector.pdf): задание, теория, `std::vector`, замеры этого стенда;
* исследование ИИ — [../AI_comparison.pdf](../AI_comparison.pdf): сравнение с Fable (`../../`), Codex (`../codex/`) и DeepSeek (`../deepseek/`), затраты.

| Файл | Что внутри |
|---|---|
| `subvector.h` | шаблон класса `subvector<T>` по заданию: поля `data / size / capacity`, `push_back`, `pop_back`, `resize`, `shrink_to_fit`, `clear`, конструктор и деструктор; стратегия роста (+c или ×k) и способ перевыделения (перенос по одному, memcpy, realloc) |
| `tests.cpp` | 3079 проверок, сборка с ASan/UBSan: `int`, `std::string`, тип-счётчик объектов, сверка со `std::vector` после каждой операции |
| `bench.cpp` | замеры: `capacity latency realloc step factor types strategies` |
| `capseq.cpp` | последовательность ёмкостей `std::vector` (libstdc++ и libc++) |
| `compare.cpp`, `compare.py` | общий стенд для Fable, Codex, DeepSeek, Claude и двух `std::vector` |
| `plot.py` | 12 графиков в `plots/` (1–9 и 11 — для отчёта по лабе, 10 и 12 — для сравнения ИИ) и сводка чисел `data/summary.json` |
| `../../report/make_pdf.py` | оба PDF: Markdown → HTML (pandoc) → PDF (Chromium) |
| `run.sh` | всё подряд, ≈15 минут |
| `data/` | все исходные CSV (`equivalence.csv` — первая версия против шаблона класса) |

Главное отличие от двух предыдущих решений: способ переноса вынесен в отдельный параметр. Видно, что «быстрый +10» у Codex получается из-за `realloc` в glibc, а разные абсолютные секунды у Fable — из-за состояния `malloc`, а не из-за кода.
