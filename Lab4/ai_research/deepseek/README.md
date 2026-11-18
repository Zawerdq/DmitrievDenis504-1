# Lab4 · решение DeepSeek

`subvector.hpp` — класс, присланный пользователем 18.11.2026. Код сохранён без изменений, к нему добавлены только шапка-комментарий и `#pragma once`. Замеров, `main()` и отчёта в присланном тексте нет.

| Файл | Кто написал | Что внутри |
|---|---|---|
| `subvector.hpp` | DeepSeek | класс `subvector`: стратегии +10, +100, ×1.5, ×2, `new[]` + цикл копирования |
| `tests.cpp` | Claude | 1022 проверки, сверка со `std::vector` через `pop_back` (другого доступа к элементам у класса нет) |
| `ub_factor.cpp` | Claude | демонстрация UB при множителе `1e300` (`-fsanitize=float-cast-overflow`) |

Разбор решения и общий стенд со всеми реализациями — раздел 7 и рис. 10 в [../AI_comparison.pdf](../AI_comparison.pdf).

```bash
g++ -std=c++17 -O1 -g -fsanitize=address,undefined,float-cast-overflow tests.cpp -o tests && ./tests
```
