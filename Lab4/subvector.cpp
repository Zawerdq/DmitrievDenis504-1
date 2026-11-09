#include "subvector.h"

#include <new>   // std::nothrow

subvector::subvector() {
    data = nullptr;
    size = 0;
    capacity = 0;
    multiply = true;
    factor = 2.0;
    step = 1;
}

subvector::~subvector() {
    delete[] data;   // delete[] nullptr допустим
}

int subvector::pop_back() {
    if (size == 0) {
        return 0;
    }
    --size;
    return data[size];
}

// Новый массив нужной ёмкости, перенос элементов, освобождение старого.
// Если память не выделилась, вектор остаётся прежним.
bool subvector::resize(unsigned int new_capacity) {
    if (new_capacity == capacity) {
        return true;
    }
    if (new_capacity == 0) {
        delete[] data;
        data = nullptr;
        size = 0;
        capacity = 0;
        return true;
    }

    int* fresh = new (std::nothrow) int[new_capacity];   // при неудаче вернёт nullptr
    if (fresh == nullptr) {
        return false;
    }

    unsigned int keep = size < new_capacity ? size : new_capacity;
    for (unsigned int i = 0; i < keep; ++i) {
        fresh[i] = data[i];
    }

    delete[] data;
    data = fresh;
    size = keep;
    capacity = new_capacity;
    return true;
}

void subvector::shrink_to_fit() {
    resize(size);
}

void subvector::clear() {
    size = 0;
}

void subvector::set_growth_factor(double new_factor) {
    multiply = true;
    factor = new_factor;
}

void subvector::set_growth_step(unsigned int new_step) {
    multiply = false;
    step = new_step;
}

bool subvector::grow() {
    unsigned int new_capacity;
    if (multiply) {
        new_capacity = (unsigned int)(capacity * factor);
    } else {
        new_capacity = capacity + step;
    }
    // При малой ёмкости умножение может не дать роста: 0 * 2 = 0, 1 * 1.5 = 1.
    if (new_capacity <= capacity) {
        new_capacity = capacity + 1;
    }
    return resize(new_capacity);
}
