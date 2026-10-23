// subvector.h — упрощённый аналог std::vector с настраиваемой стратегией роста ёмкости.
#pragma once

#include <algorithm>
#include <cstddef>
#include <limits>
#include <new>
#include <utility>

// Стратегия роста: во сколько раз умножать capacity или сколько к ней прибавлять,
// когда push_back выходит за границу выделенной памяти.
struct Growth {
    enum Kind { Add, Mul };
    Kind kind;
    double factor;      // для Mul: новая ёмкость = ceil(capacity * factor) (минимум +1)
    unsigned int step;  // для Add: новая ёмкость = capacity + step

    static Growth add(unsigned int step) { return Growth{Add, 1.0, step}; }
    static Growth mul(double factor) { return Growth{Mul, factor, 0}; }

    // Следующая ёмкость после old_cap. Возвращает 0 при переполнении unsigned int.
    unsigned int next(unsigned int old_cap) const {
        const unsigned long long maxv = std::numeric_limits<unsigned int>::max();
        unsigned long long n;
        if (kind == Add) {
            n = static_cast<unsigned long long>(old_cap) + std::max(1u, step);
        } else {
            long double x = static_cast<long double>(old_cap) * factor;
            n = static_cast<unsigned long long>(x);
            if (static_cast<long double>(n) < x) ++n;            // округление вверх
            if (n <= old_cap) n = static_cast<unsigned long long>(old_cap) + 1;  // гарантированный рост
        }
        return n > maxv ? 0u : static_cast<unsigned int>(n);
    }
};

// Счётчики для анализа (не влияют на поведение контейнера).
struct SubvectorStats {
    unsigned long long reallocations = 0;  // сколько раз выделялся новый буфер
    unsigned long long moved_elements = 0; // сколько элементов перенесено при перевыделениях
};

template <typename T>
class subvector {
public:
    subvector() : data(nullptr), size(0), capacity(0), growth_(Growth::mul(2.0)) {}
    explicit subvector(Growth g) : data(nullptr), size(0), capacity(0), growth_(g) {}

    ~subvector() { delete[] data; }

    subvector(const subvector& o) : data(nullptr), size(0), capacity(0), growth_(o.growth_) {
        if (o.size > 0) {
            data = new T[o.size];  // как у std::vector: копия получает capacity == size
            std::copy(o.data, o.data + o.size, data);
            size = capacity = o.size;
        }
    }
    subvector(subvector&& o) noexcept
        : data(o.data), size(o.size), capacity(o.capacity), growth_(o.growth_), stats_(o.stats_) {
        o.data = nullptr;
        o.size = o.capacity = 0;
    }
    subvector& operator=(subvector o) noexcept {  // copy-and-swap
        swap(o);
        return *this;
    }
    void swap(subvector& o) noexcept {
        std::swap(data, o.data);
        std::swap(size, o.size);
        std::swap(capacity, o.capacity);
        std::swap(growth_, o.growth_);
        std::swap(stats_, o.stats_);
    }

    // Добавляет d в конец; при нехватке места увеличивает ёмкость по стратегии.
    // false — если память выделить не удалось (вектор не изменился).
    bool push_back(const T& d) {
        if (size == capacity) {
            unsigned int nc = growth_.next(capacity);
            if (nc == 0 || !resize(nc)) return false;
        }
        data[size++] = d;
        return true;
    }

    // Удаляет последний элемент и возвращает его; для пустого вектора — T{} (для int это 0).
    T pop_back() {
        if (size == 0) return T{};
        return data[--size];
    }

    // Меняет ёмкость. Если new_capacity < size, лишние элементы отбрасываются.
    // false — если не удалось выделить память (вектор не изменился).
    bool resize(unsigned int new_capacity) {
        if (new_capacity == capacity) return true;
        T* nd = nullptr;
        if (new_capacity > 0) {
            nd = new (std::nothrow) T[new_capacity];
            if (!nd) return false;
        }
        unsigned int keep = std::min(size, new_capacity);
        for (unsigned int i = 0; i < keep; ++i) nd[i] = std::move(data[i]);
        delete[] data;
        data = nd;
        size = keep;
        capacity = new_capacity;
        ++stats_.reallocations;
        stats_.moved_elements += keep;
        return true;
    }

    // Освобождает неиспользуемую память: capacity становится равной size.
    void shrink_to_fit() { resize(size); }

    // Удаляет элементы, ёмкость сохраняется.
    void clear() { size = 0; }

    // Удобства для проверок и экспериментов.
    unsigned int get_size() const { return size; }
    unsigned int get_capacity() const { return capacity; }
    bool empty() const { return size == 0; }
    T& operator[](unsigned int i) { return data[i]; }
    const T& operator[](unsigned int i) const { return data[i]; }
    const SubvectorStats& stats() const { return stats_; }
    const Growth& growth() const { return growth_; }

private:
    // Поля из задания. В описании методов size также называется top.
    T* data;
    unsigned int size;
    unsigned int capacity;

    Growth growth_;
    SubvectorStats stats_;
};
