#include "subvector.h"

#include <cmath>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>

static const unsigned int MAX_CAP = std::numeric_limits<unsigned int>::max();

bool init(subvector* qv) {
    qv->mas = nullptr;
    qv->top = 0;
    qv->capacity = 0;
    qv->growth = Growth{};
    qv->how = Realloc::NewLoop;
    return true;
}

int pop_back(subvector* qv) {
    if (qv->top == 0) return 0;
    return qv->mas[--qv->top];
}

static void release(subvector* qv) {
    if (qv->how == Realloc::CRealloc) std::free(qv->mas);
    else delete[] qv->mas;
    qv->mas = nullptr;
}

// Главная операция: новый массив new_capacity, перенос min(top, new_capacity) элементов, освобождение старого.
// При неудаче выделения структура не меняется и возвращается false.
bool resize(subvector* qv, unsigned int new_capacity) {
    if (new_capacity == qv->capacity) return true;
    unsigned int keep = qv->top < new_capacity ? qv->top : new_capacity;
    if (new_capacity == 0) {
        release(qv);
        qv->top = qv->capacity = 0;
        return true;
    }
    int* fresh = nullptr;
    switch (qv->how) {
    case Realloc::CRealloc:
        // realloc может расширить блок на месте или (для больших блоков в glibc) переставить
        // страницы через mremap — тогда элементы вообще не копируются.
        fresh = static_cast<int*>(std::realloc(qv->mas, std::size_t(new_capacity) * sizeof(int)));
        if (!fresh) return false;
        break;
    case Realloc::NewMemcpy:
        fresh = new (std::nothrow) int[new_capacity];
        if (!fresh) return false;
        if (keep) std::memcpy(fresh, qv->mas, std::size_t(keep) * sizeof(int));
        delete[] qv->mas;
        break;
    case Realloc::NewLoop:
        fresh = new (std::nothrow) int[new_capacity];
        if (!fresh) return false;
        for (unsigned int i = 0; i < keep; ++i) fresh[i] = qv->mas[i];
        delete[] qv->mas;
        break;
    }
    qv->mas = fresh;
    qv->top = keep;
    qv->capacity = new_capacity;
    return true;
}

void shrink_to_fit(subvector* qv) { resize(qv, qv->top); }

void clear(subvector* qv) { qv->top = 0; }

void destructor(subvector* qv) {
    release(qv);
    Growth g = qv->growth;
    Realloc h = qv->how;
    init(qv);
    qv->growth = g;     // стратегия — настройка объекта, а не данные; после очистки её сохраняем
    qv->how = h;
}

void set_growth_factor(subvector* qv, double k) {
    if (!(k > 1.0) || !std::isfinite(k)) k = 2.0;   // недопустимый множитель -> по умолчанию
    qv->growth.multiply = true;
    qv->growth.factor = k;
}

void set_growth_step(subvector* qv, unsigned int c) {
    qv->growth.multiply = false;
    qv->growth.step = c ? c : 1;
}

void set_realloc(subvector* qv, Realloc how) {
    // менять способ можно только у пустого объекта: new[] и malloc нельзя смешивать
    if (qv->mas == nullptr) qv->how = how;
}

unsigned int next_capacity(const Growth& g, unsigned int cap) {
    double want;
    if (g.multiply) want = cap == 0 ? 1.0 : std::ceil(double(cap) * g.factor);
    else want = double(cap) + g.step;
    if (want > double(MAX_CAP)) want = MAX_CAP;           // защита от переполнения unsigned
    unsigned int next = static_cast<unsigned int>(want);
    return next > cap ? next : cap + 1;                    // рост хотя бы на 1 (1 * 1.5 -> 2)
}

bool grow_slow(subvector* qv) {
    if (qv->capacity == MAX_CAP) return false;
    return resize(qv, next_capacity(qv->growth, qv->capacity));
}
