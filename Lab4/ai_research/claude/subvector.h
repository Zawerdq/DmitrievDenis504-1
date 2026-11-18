// Lab4 · subvector — решение Claude.
//
// Шаблон класса, как просит задание: поля data / size / capacity, методы push_back, pop_back,
// resize (меняет ЁМКОСТЬ), shrink_to_fit, clear, конструктор пустого вектора и деструктор.
// Работает для любого T, не только для int: память выделяется «сырой» (malloc), элементы
// конструируются на месте и переносятся через move_if_noexcept — как в std::vector.
//
// Для экспериментов добавлены две настройки:
//   Growth  — стратегия роста при переполнении: прибавлять c или умножать на k;
//   Realloc — чем перевыделять память: новый блок + поэлементный перенос (по умолчанию),
//             новый блок + memcpy, или realloc. Два последних допустимы только для тривиально
//             копируемых T (int и т.п.); для остальных типов молча используется перенос по одному.
#ifndef CLAUDE_SUBVECTOR_H
#define CLAUDE_SUBVECTOR_H

#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>
#include <type_traits>
#include <utility>

enum class Realloc { NewLoop, NewMemcpy, CRealloc };

struct Growth {
    bool multiply = true;     // true: capacity * factor, false: capacity + step
    double factor = 2.0;
    unsigned int step = 0;

    static Growth add(unsigned int c) { Growth g; g.multiply = false; g.step = c ? c : 1; return g; }
    static Growth mul(double k) {
        Growth g;
        g.factor = (k > 1.0 && std::isfinite(k)) ? k : 2.0;   // недопустимый множитель -> 2
        return g;
    }
};

// Какую ёмкость взять при переполнении. Считается в double, округляется вверх, ограничена UINT_MAX
// и всегда хотя бы на 1 больше: без этого 1 * 1.5 = 1 и 0 * 2 = 0 зациклили бы рост.
inline unsigned int next_capacity(const Growth& g, unsigned int cap) {
    const double max_cap = double(std::numeric_limits<unsigned int>::max());
    double want = g.multiply ? (cap == 0 ? 1.0 : std::ceil(double(cap) * g.factor)) : double(cap) + g.step;
    if (!(want <= max_cap)) want = max_cap;                   // заодно отсекает NaN
    unsigned int next = static_cast<unsigned int>(want);
    return next > cap ? next : cap + 1;
}

template <class T = int>
class subvector {
    static_assert(alignof(T) <= alignof(std::max_align_t), "malloc не гарантирует выравнивание для over-aligned T");
public:
    subvector() = default;                                    // пустой: data = nullptr, size = capacity = 0
    explicit subvector(Growth g, Realloc how = Realloc::NewLoop) : growth(g), how(fast_ok ? how : Realloc::NewLoop) {}
    ~subvector() { release(); }

    // Глубокая копия (ёмкость = size, как у std::vector) и перемещение (забирает блок).
    subvector(const subvector& o) : growth(o.growth), how(o.how) {
        if (!resize(o.size)) throw std::bad_alloc();
        for (unsigned int i = 0; i < o.size; ++i) push_back(o.data[i]);
    }
    subvector(subvector&& o) noexcept { swap(o); }
    subvector& operator=(subvector o) noexcept { swap(o); return *this; }   // copy-and-swap
    void swap(subvector& o) noexcept {
        std::swap(data, o.data); std::swap(size, o.size); std::swap(capacity, o.capacity);
        std::swap(growth, o.growth); std::swap(how, o.how);
    }

    // Добавить в конец. Если места нет — увеличить ёмкость по стратегии. false, если память не выделилась.
    bool push_back(const T& d) {
        if (size == capacity) return grow_and_push(d);
        ::new (static_cast<void*>(data + size)) T(d);
        ++size;
        return true;
    }
    bool push_back(T&& d) {
        if (size == capacity) return grow_and_push(std::move(d));
        ::new (static_cast<void*>(data + size)) T(std::move(d));
        ++size;
        return true;
    }

    // Удалить последний и вернуть его. Пустой вектор — вернуть T() (для int это 0).
    T pop_back() {
        if (size == 0) return T();
        --size;
        T out(std::move(data[size]));
        data[size].~T();
        return out;
    }

    // Изменить ёмкость. Если new_capacity < size, лишние элементы уничтожаются (данные обрезаются).
    // При неудаче выделения вектор не меняется и возвращается false (строгая гарантия).
    bool resize(unsigned int new_capacity) {
        if (new_capacity == capacity) return true;
        const unsigned int keep = size < new_capacity ? size : new_capacity;
        if (new_capacity == 0) { release(); return true; }

        if (fast_ok && how == Realloc::CRealloc) {            // только для тривиально копируемых T
            if (!realloc_block(new_capacity)) return false;
        } else {
            T* fresh = static_cast<T*>(std::malloc(std::size_t(new_capacity) * sizeof(T)));
            if (!fresh) return false;
            if (fast_ok && how == Realloc::NewMemcpy) {
                copy_bytes(fresh, keep);
            } else {
                unsigned int i = 0;
                try {                                         // перенос по одному: move, если он noexcept, иначе копия
                    for (; i < keep; ++i) ::new (static_cast<void*>(fresh + i)) T(std::move_if_noexcept(data[i]));
                } catch (...) {
                    while (i) fresh[--i].~T();
                    std::free(fresh);
                    throw;
                }
            }
            destroy(0, size);
            std::free(data);
            data = fresh;
        }
        size = keep;
        capacity = new_capacity;
        return true;
    }

    void shrink_to_fit() { resize(size); }                     // capacity = size
    void clear() { destroy(0, size); size = 0; }               // элементы уничтожены, память та же

    // Доступ к данным (только чтение размера/ёмкости; поля закрыты, чтобы не нарушить инвариант).
    unsigned int get_size() const { return size; }
    unsigned int get_capacity() const { return capacity; }
    T& operator[](unsigned int i) { return data[i]; }          // i < size
    const T& operator[](unsigned int i) const { return data[i]; }
    const T* get_data() const { return data; }

    void set_growth(Growth g) { growth = g; }
    void set_realloc(Realloc h) { if (data == nullptr) how = fast_ok ? h : Realloc::NewLoop; }  // только у пустого

private:
    static constexpr bool fast_ok = std::is_trivially_copyable<T>::value;

    // Побайтовые операции компилируются только для тривиально копируемых T (if constexpr).
    bool realloc_block(unsigned int new_capacity) {
        if constexpr (fast_ok) {
            void* p = std::realloc(data, std::size_t(new_capacity) * sizeof(T));
            if (!p) return false;
            data = static_cast<T*>(p);
            return true;
        } else {
            return false;
        }
    }
    void copy_bytes(T* fresh, unsigned int keep) {
        if constexpr (fast_ok) {
            if (keep) std::memcpy(fresh, data, std::size_t(keep) * sizeof(T));
        }
    }

    template <class U>
    bool grow_and_push(U&& d) {                                // редкий путь: вынесен из горячего цикла
        if (capacity == std::numeric_limits<unsigned int>::max()) return false;
        // d может ссылаться на элемент самого вектора (v.push_back(v[0])): копируем до перевыделения
        T tmp(std::forward<U>(d));
        if (!resize(next_capacity(growth, capacity))) return false;
        ::new (static_cast<void*>(data + size)) T(std::move(tmp));
        ++size;
        return true;
    }
    void destroy(unsigned int from, unsigned int to) {
        if (!std::is_trivially_destructible<T>::value)
            for (unsigned int i = from; i < to; ++i) data[i].~T();
    }
    void release() {
        destroy(0, size);
        std::free(data);
        data = nullptr;
        size = capacity = 0;
    }

    T* data = nullptr;                 // начало выделенной памяти
    unsigned int size = 0;             // сколько элементов лежит
    unsigned int capacity = 0;         // сколько помещается без перевыделения
    Growth growth;                     // стратегия роста
    Realloc how = Realloc::NewLoop;    // способ перевыделения
};

#endif
