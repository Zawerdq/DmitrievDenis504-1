// Решение DeepSeek, присланное пользователем 18.11.2026. Код ниже приведён без изменений
// (добавлены только эта шапка и #pragma once). Отчёт, замеры и main() автора в присланном тексте отсутствуют.
#pragma once
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <new>
#include <string>
#include <vector>

class subvector {
public:
    enum class Strategy { Plus10, Plus100, Mul15, Mul2 };

private:
    int* data_ = nullptr;
    unsigned int size_ = 0;
    unsigned int capacity_ = 0;

    bool use_mul_ = true;
    double factor_ = 2.0;
    unsigned int add_ = 0;

    static unsigned int next_mul(unsigned int cap, double f) {
        if (cap == 0) return 1;
        unsigned int nxt = static_cast<unsigned int>(std::ceil(cap * f));
        if (nxt <= cap) nxt = cap + 1;
        return nxt;
    }

    static unsigned int next_add(unsigned int cap, unsigned int add) {
        if (add == 0) add = 1;
        return cap + add;
    }

    unsigned int next_capacity() const {
        return use_mul_ ? next_mul(capacity_, factor_)
                        : next_add(capacity_, add_);
    }

public:
    explicit subvector(Strategy s = Strategy::Mul2) {
        set_strategy(s);
    }

    explicit subvector(double factor) : use_mul_(true), factor_(factor) {}

    explicit subvector(unsigned int add) : use_mul_(false), add_(add) {}

    subvector(const subvector&) = delete;
    subvector& operator=(const subvector&) = delete;

    ~subvector() {
        delete[] data_;
    }

    void set_strategy(Strategy s) {
        switch (s) {
        case Strategy::Plus10:  use_mul_ = false; add_ = 10;  break;
        case Strategy::Plus100: use_mul_ = false; add_ = 100; break;
        case Strategy::Mul15:   use_mul_ = true;  factor_ = 1.5; break;
        case Strategy::Mul2:    use_mul_ = true;  factor_ = 2.0; break;
        }
    }

    bool push_back(int d) {
        if (size_ == capacity_) {
            if (!resize(next_capacity())) return false;
        }
        data_[size_++] = d;
        return true;
    }

    int pop_back() {
        if (size_ == 0) return 0;
        return data_[--size_];
    }

    bool resize(unsigned int new_capacity) {
        if (new_capacity == capacity_) {
            if (new_capacity < size_) size_ = new_capacity;
            return true;
        }

        int* new_data = nullptr;
        if (new_capacity > 0) {
            new_data = new (std::nothrow) int[new_capacity];
            if (!new_data) return false;
        }

        unsigned int to_copy = std::min(size_, new_capacity);
        for (unsigned int i = 0; i < to_copy; ++i) {
            new_data[i] = data_[i];
        }

        delete[] data_;
        data_ = new_data;
        capacity_ = new_capacity;
        if (size_ > capacity_) size_ = capacity_;
        return true;
    }

    void shrink_to_fit() {
        if (capacity_ != size_) resize(size_);
    }

    void clear() {
        size_ = 0;
    }

    unsigned int size() const { return size_; }
    unsigned int capacity() const { return capacity_; }
};
