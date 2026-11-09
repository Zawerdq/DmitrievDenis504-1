#ifndef SUBVECTOR_H
#define SUBVECTOR_H

// Упрощённый аналог std::vector для int.
// Владеет динамическим массивом data: выделяет его через new[], освобождает через delete[].
class subvector {
public:
    subvector();     // пустой вектор: data == nullptr, size == 0, capacity == 0
    ~subvector();    // освобождает память

    // Обычная копия скопировала бы только адрес, и два объекта освобождали бы один массив.
    // Поэтому копирование запрещено.
    subvector(const subvector&) = delete;
    subvector& operator=(const subvector&) = delete;

    // Добавить элемент в конец. Если места нет, сначала увеличить ёмкость.
    // Возвращает false, если память выделить не удалось.
    // Определён в заголовке, чтобы компилятор мог встроить его в цикл,
    // как он делает это с push_back у std::vector.
    bool push_back(int d) {
        if (size == capacity && !grow()) {
            return false;
        }
        data[size] = d;
        ++size;
        return true;
    }

    int pop_back();                           // удалить последний и вернуть его; для пустого вернуть 0
    bool resize(unsigned int new_capacity);   // изменить ёмкость; если она меньше size, данные обрезаются
    void shrink_to_fit();                     // уменьшить ёмкость до size
    void clear();                             // убрать элементы, ёмкость не менять

    // Стратегия роста при переполнении. По умолчанию ёмкость удваивается.
    void set_growth_factor(double factor);    // capacity = capacity * factor
    void set_growth_step(unsigned int step);  // capacity = capacity + step

    unsigned int get_size() const { return size; }
    unsigned int get_capacity() const { return capacity; }
    int get(unsigned int index) const { return data[index]; }   // index < size

private:
    bool grow();              // увеличить ёмкость по выбранной стратегии

    int* data;                // начало выделенной памяти
    unsigned int size;        // сколько элементов хранится
    unsigned int capacity;    // сколько элементов помещается без перевыделения

    bool multiply;            // true: умножать ёмкость, false: прибавлять к ней
    double factor;            // множитель
    unsigned int step;        // слагаемое
};

#endif
