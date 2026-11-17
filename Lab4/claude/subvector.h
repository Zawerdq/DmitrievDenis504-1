// Lab4 · subvector («недовектор»): решение Claude.
//
// Интерфейс повторяет задание дословно: структура с тремя полями (mas, top, capacity)
// и свободные функции init / push_back / pop_back / resize / shrink_to_fit / clear / destructor.
// К заданию добавлено одно: стратегия роста (прибавлять c или умножать на k) и способ
// перевыделения памяти (new[] + цикл, new[] + memcpy, realloc). Способ нужен только для
// эксперимента, который объясняет, почему у разных авторов «+10» то медленный, то быстрый.
#ifndef CLAUDE_SUBVECTOR_H
#define CLAUDE_SUBVECTOR_H

enum class Realloc { NewLoop, NewMemcpy, CRealloc };

struct Growth {
    bool multiply = true;   // true: capacity * factor, false: capacity + step
    double factor = 2.0;
    unsigned int step = 0;
};

struct subvector {
    int* mas;                 // начало выделенного массива (nullptr, если capacity == 0)
    unsigned int top;         // сколько элементов лежит (то же, что size у std::vector)
    unsigned int capacity;    // сколько помещается без перевыделения
    Growth growth;            // стратегия роста при переполнении
    Realloc how;              // чем перевыделять память
};

// --- функции из задания ---
bool init(subvector* qv);                                  // пустой: mas = nullptr, top = capacity = 0
// bool push_back(subvector* qv, int d);                   // добавить в конец (определена ниже, inline)
int  pop_back(subvector* qv);                              // удалить последний и вернуть его; пустой -> 0
bool resize(subvector* qv, unsigned int new_capacity);     // сменить ёмкость; лишнее (top > new) отбрасывается
void shrink_to_fit(subvector* qv);                         // capacity = top
void clear(subvector* qv);                                 // top = 0, память не трогаем
void destructor(subvector* qv);                            // освободить память, снова пустой

// --- дополнения для экспериментов ---
void set_growth_factor(subvector* qv, double k);           // k > 1
void set_growth_step(subvector* qv, unsigned int c);       // c > 0
void set_realloc(subvector* qv, Realloc how);
unsigned int next_capacity(const Growth& g, unsigned int cap);   // какую ёмкость выбрать при переполнении

bool grow_slow(subvector* qv);                             // редкий путь push_back (вынесен из горячего цикла)

// push_back определён в заголовке: как и у std::vector, быстрый путь должен встраиваться в цикл.
inline bool push_back(subvector* qv, int d) {
    if (qv->top == qv->capacity && !grow_slow(qv)) return false;
    qv->mas[qv->top++] = d;
    return true;
}

#endif
