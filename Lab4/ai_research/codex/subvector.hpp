#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <limits>
#include <stdexcept>
#include <utility>

class Growth {
    unsigned step_;
    double factor_;
    Growth(unsigned step, double factor) : step_(step), factor_(factor) {}

public:
    static Growth add(unsigned step) {
        if (step == 0) throw std::invalid_argument("step must be positive");
        return Growth(step, 0);
    }
    static Growth multiply(double factor) {
        if (!std::isfinite(factor) || factor <= 1)
            throw std::invalid_argument("factor must be finite and exceed one");
        return Growth(0, factor);
    }
    unsigned next(unsigned old, unsigned limit) const noexcept {
        if (step_) return old + std::min(step_, limit - old);
        if (old == 0) return 1;
        const double target = std::ceil(old * factor_);
        if (target >= limit) return limit;
        return std::max(old + 1, static_cast<unsigned>(target));
    }
};

class subvector {
    Growth growth_;
    int* data_ = nullptr;
    unsigned size_ = 0;
    unsigned capacity_ = 0;

public:
    explicit subvector(Growth growth = Growth::multiply(2)) : growth_(growth) {}
    ~subvector() { std::free(data_); }
    subvector(const subvector&) = delete;
    subvector& operator=(const subvector&) = delete;
    subvector(subvector&& other) noexcept : subvector(other.growth_) { swap(other); }
    subvector& operator=(subvector&& other) noexcept {
        subvector tmp(std::move(other));
        swap(tmp);
        return *this;
    }
    void swap(subvector& other) noexcept {
        std::swap(growth_, other.growth_);
        std::swap(data_, other.data_);
        std::swap(size_, other.size_);
        std::swap(capacity_, other.capacity_);
    }
    const int* data() const noexcept { return data_; }
    unsigned size() const noexcept { return size_; }
    unsigned capacity() const noexcept { return capacity_; }
    static constexpr unsigned max_capacity() noexcept {
        return static_cast<unsigned>(std::min<std::size_t>(
            std::numeric_limits<unsigned>::max(),
            std::numeric_limits<std::size_t>::max() / sizeof(int)));
    }
    bool resize(unsigned wanted) noexcept {
        if (wanted == capacity_) return true;
        if (wanted > max_capacity()) return false;
        if (wanted == 0) {
            std::free(data_);
            data_ = nullptr;
        } else {
            void* memory = std::realloc(data_, std::size_t(wanted) * sizeof(int));
            if (!memory) return false;
            data_ = static_cast<int*>(memory);
        }
        capacity_ = wanted;
        size_ = std::min(size_, wanted);
        return true;
    }
    bool push_back(int value) noexcept {
        if (size_ == capacity_) {
            if (size_ == max_capacity() || !resize(growth_.next(capacity_, max_capacity())))
                return false;
        }
        data_[size_++] = value;
        return true;
    }
    int pop_back() noexcept { return size_ ? data_[--size_] : 0; }
    void clear() noexcept { size_ = 0; }
    void shrink_to_fit() noexcept { resize(size_); }
};
