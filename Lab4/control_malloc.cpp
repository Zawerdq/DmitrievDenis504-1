// control_malloc.cpp — контрольный опыт: когда glibc отдаёт большой блок через mmap
// (свежие страницы, page fault на каждую), а когда из уже затронутой кучи.
//
//   g++ -std=c++17 -O2 control_malloc.cpp -o control_malloc && ./control_malloc
//
// Барьеры asm volatile нужны, чтобы компилятор не выбросил malloc/memset/free целиком
// (без них g++ -O2 так и делает, и опыт ничего не измеряет).
#include <malloc.h>
#include <sys/resource.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static long faults() {
    rusage r{};
    getrusage(RUSAGE_SELF, &r);
    return r.ru_minflt;
}

static void touch(char* p, std::size_t n) {
    asm volatile("" : : "r"(p) : "memory");
    std::memset(p, 1, n);
    asm volatile("" : : "r"(p) : "memory");
}

static void heap_state(const char* tag) {
    struct mallinfo2 mi = mallinfo2();
    std::printf("  [%s] куча %.1f МБ, свободно в куче %.1f МБ, из них вершина %.1f МБ\n", tag, mi.arena / 1048576.0,
                mi.fordblks / 1048576.0, mi.keepcost / 1048576.0);
}

// Выделить mb мегабайт, заполнить, напечатать page faults и откуда взят блок, освободить.
static void probe(const char* tag, std::size_t mb) {
    std::size_t sz = mb << 20;
    long f0 = faults();
    char* p = static_cast<char*>(std::malloc(sz));
    touch(p, sz);
    long df = faults() - f0;
    struct mallinfo2 mi = mallinfo2();
    std::printf("  %-46s %3zu МБ: page faults %6ld, через mmap: %s\n", tag, mb, df, mi.hblks ? "да" : "нет");
    asm volatile("" : : "r"(p) : "memory");
    std::free(p);
}

int main() {
    std::puts("1. Динамический порог mmap (glibc, 64 бита: от 128 КБ, растёт до 32 МБ при освобождении mmap-блоков)");
    probe("16 МБ в свежем процессе", 16);
    probe("16 МБ повторно (порог уже поднят до 16 МБ)", 16);
    probe("30 МБ впервые", 30);
    probe("30 МБ повторно", 30);
    probe("40 МБ (> 32 МБ, порог выше не поднимается)", 40);
    probe("40 МБ повторно", 40);

    std::puts("\n2. Блок больше порога берётся из кучи, если там есть непрерывный свободный кусок нужного размера");
    for (int variant = 0; variant < 2; ++variant) {
        const int chunks = variant == 0 ? 500 : 580;  // ~49 МБ и ~57 МБ мелких блоков по 100 КБ
        std::vector<char*> v;
        for (int i = 0; i < chunks; ++i) {
            char* p = static_cast<char*>(std::malloc(100u << 10));
            touch(p, 100u << 10);
            v.push_back(p);
        }
        for (auto it = v.rbegin(); it != v.rend(); ++it) std::free(*it);
        std::printf(" вариант %d: освобождено %d блоков по 100 КБ\n", variant + 1, chunks);
        heap_state("до запроса");
        probe("40 МБ", 40);
        probe("40 МБ повторно", 40);
    }
    return 0;
}
