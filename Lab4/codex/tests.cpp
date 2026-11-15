#include "subvector.hpp"
#include <iostream>
#include <random>
#include <source_location>
#include <string>
#include <vector>

void check(bool ok, std::source_location where = std::source_location::current()) {
    if (!ok) throw std::runtime_error("check failed at line " + std::to_string(where.line()));
}

int main() {
    check(Growth::add(10).next(95, 100) == 100);
    check(Growth::multiply(1.5).next(3, 100) == 5);
    check(Growth::multiply(1e300).next(2, 100) == 100);
    for (auto value : {0.0, 1.0, -2.0, std::numeric_limits<double>::infinity(),
                       std::numeric_limits<double>::quiet_NaN()}) {
        bool rejected = false;
        try { Growth::multiply(value); }
        catch (const std::invalid_argument&) { rejected = true; }
        check(rejected);
    }
    bool rejected = false;
    try { Growth::add(0); }
    catch (const std::invalid_argument&) { rejected = true; }
    check(rejected);
    subvector fractional(Growth::multiply(1.5));
    for (unsigned capacity : {1u, 2u, 3u, 5u, 5u, 8u}) {
        check(fractional.push_back(3) && fractional.capacity() == capacity);
    }
    subvector empty;
    check(!empty.data() && !empty.capacity() && !empty.size() && !empty.pop_back());
    for (auto policy : {Growth::add(10), Growth::add(100),
                        Growth::multiply(1.5), Growth::multiply(2)}) {
        subvector v(policy);
        std::vector<int> expected;
        std::mt19937 rng(17);
        for (int i = 0; i < 10000; ++i) {
            unsigned cap = v.capacity();
            switch (rng() % 9) {
            case 0: {
                unsigned wanted = rng() % 128;
                check(v.resize(wanted) && v.capacity() == wanted);
                if (wanted < expected.size()) expected.resize(wanted);
                break;
            }
            case 1:
                v.clear(); expected.clear(); check(v.capacity() == cap); break;
            case 2:
                v.shrink_to_fit(); check(v.capacity() == v.size()); break;
            case 3:
                check(v.pop_back() == (expected.empty() ? 0 : expected.back()));
                if (!expected.empty()) expected.pop_back();
                break;
            default:
                check(v.push_back(i)); expected.push_back(i);
            }
            check(v.size() == expected.size() && v.capacity() >= v.size());
            check(std::equal(expected.begin(), expected.end(), v.data()));
        }
        v.clear(); check(v.push_back(41));
        subvector moved(std::move(v));
        check(!v.data() && !v.size() && !v.capacity() && v.push_back(7));
        v = std::move(moved);
        check(!moved.data() && v.pop_back() == 41);
    }
    std::cout << "All checks passed\n";
}
