# Лабораторная 4. subvector: динамический массив и стратегии роста

Отчёт с графиками и выводами: [REPORT.md](REPORT.md).

## Файлы

| Файл | Что внутри |
|---|---|
| `subvector.h` | класс `subvector` (поля `data`, `size`, `capacity`), `push_back` |
| `subvector.cpp` | конструктор, деструктор, `pop_back`, `resize`, `shrink_to_fit`, `clear`, выбор стратегии роста |
| `tests.cpp` | проверки корректности, в том числе сверка со `std::vector` на 200 000 случайных операций |
| `main.cpp` | все опыты: поведение `std::vector`, сравнение стратегий, развёртки по множителю и по слагаемому |
| `run.sh` | полный прогон: проверки, сборка, опыты, графики |
| `plot.py` | медианы и разброс (`data/summary_*.csv`), графики (`plots/*.png`) |
| `data/` | исходные CSV с каждым замером и сводные таблицы |
| `plots/` | графики |

## Интерфейс subvector

```cpp
subvector v;                              // пустой: data == nullptr, size == 0, capacity == 0

bool push_back(int d);                    // добавить в конец; false, если память не выделилась
int  pop_back();                          // удалить последний и вернуть его; для пустого вернуть 0
bool resize(unsigned int new_capacity);   // изменить ёмкость; если она меньше size, данные обрезаются
void shrink_to_fit();                     // capacity = size
void clear();                             // size = 0, capacity не меняется

void set_growth_factor(double factor);    // при переполнении capacity = capacity * factor (по умолчанию 2)
void set_growth_step(unsigned int step);  // при переполнении capacity = capacity + step

unsigned int get_size() const;
unsigned int get_capacity() const;
int get(unsigned int index) const;        // index < size
```

Замечания:

- `resize` меняет **ёмкость**, как сказано в задании. У `std::vector` метод с таким именем меняет число элементов.
- В задании количество элементов названо и `size`, и `top`; в классе это одно поле `size`.
- Класс написан для `int`, без шаблона.
- Владелец массива - сам объект: память выделяется через `new[]` в `resize`, освобождается через `delete[]`
  в `resize` и в деструкторе. Копирование объекта запрещено (`= delete`): обычная копия скопировала бы
  только адрес, и два объекта освободили бы один массив дважды.
- `push_back` определён в заголовке, чтобы компилятор мог встроить его в цикл так же, как `push_back`
  у `std::vector`. Иначе сравнение времени было бы нечестным.

## Сборка и запуск

Всё сразу (около 4 минут, почти всё время уходит на медленные стратегии +10 и +100):

```bash
./run.sh
```

Вручную:

```bash
g++ -std=c++17 -O0 tests.cpp subvector.cpp -o tests && ./tests

g++ -std=c++17 -O2 main.cpp subvector.cpp -o bench
mkdir -p data plots
./bench               # все части подряд
./bench capacity      # или по одной: capacity, strategies, factor, step
python3 plot.py
```

## Методика

- Время измеряется функцией `get_time` из задания (`std::chrono::steady_clock`).
- В замер входит только цикл из n вызовов `push_back`. Создание пустого вектора, его уничтожение
  и запись в файл находятся вне таймера.
- После замера несколько элементов и размер складываются в число `result` и пишутся в CSV, чтобы
  заполнение было нужно программе.
- Каждая точка измеряется 5 раз. Порядок стратегий меняется от измерения к измерению.
  Если один замер длится больше 2 секунд, точка измеряется один раз (в таблицах отчёта помечено звёздочкой).
- Число перевыделений, число перенесённых элементов и итоговая ёмкость считаются отдельным проходом
  без таймера: программа сравнивает `capacity` до и после каждого `push_back`.

## Формат данных

| Файл | Столбцы |
|---|---|
| `capacity.csv` | `container,size,capacity`: точки, в которых ёмкость изменилась |
| `std_constructors.csv` | `case,size,capacity`: что дают конструкторы и методы `std::vector` |
| `strategies.csv` | `strategy,n,trial,seconds,result` |
| `factor.csv`, `step.csv` | `factor` или `step`, затем `n,trial,seconds,result` |
| `factor_counts.csv`, `step_counts.csv` | параметр, `n,reallocations,copied_elements,final_capacity` |
| `summary_*.csv` | медиана, минимум и максимум времени в секундах |

## Платформа измерений

| | |
|---|---|
| Процессор | Intel Xeon 2.10 ГГц, виртуальная машина, 2 ядра |
| ОС | Ubuntu 24.04, Linux 6.18 |
| Компилятор и библиотека | g++ 13.3.0, libstdc++ |
| Ключи | `-std=c++17 -O2` для опытов, `-O0` для проверок |

На другом компьютере числа будут другими, а у другого компилятора `std::vector` может расти иначе.
Чтобы повторить опыты, достаточно запустить `./run.sh`.
