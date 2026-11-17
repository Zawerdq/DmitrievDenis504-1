// Последовательность ёмкостей std::vector<int> при push_back. Собирается с libstdc++ и с libc++.
#include <cstdio>
#include <vector>

int main() {
    std::vector<int> v;
    std::size_t last = v.capacity();
    std::printf("size,capacity\n0,%zu\n", last);
    for (unsigned i = 0; i < 20000000; ++i) {
        v.push_back(int(i));
        if (v.capacity() != last) { last = v.capacity(); std::printf("%zu,%zu\n", v.size(), last); }
    }
}
