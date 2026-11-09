// Запуск опытов. Исследуемые функции лежат в text.cpp, здесь только вызовы и замеры.
//
//   ./research S O2   - скаляр (unsigned int): значение, ссылка, указатель
//   ./research A O2   - опыт A для Block и Text при текущем BLOCK_SIZE
//   ./research B O2   - опыт B: borrow / copy_each / copy_once и счётчики памяти
//
// Второй аргумент - подпись сборки (O0 или O2), она просто записывается в CSV.
#include <chrono>
#include <cstddef>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>

#include "data.h"
#include "text.h"

const int TRIALS = 7;                 // измерений каждого условия (плюс один прогрев)
const int VALUE = 0, REF = 1, PTR = 2;
const char* PASS_NAMES[3] = {"value", "ref", "ptr"};

double seconds_between(std::chrono::steady_clock::time_point start,
                       std::chrono::steady_clock::time_point finish) {
    return std::chrono::duration<double>(finish - start).count();
}

void write_header(std::ofstream& file) {
    file << std::setprecision(17);
    file << "experiment,length,mode,work,repeats,uses,opt,trial,seconds,result\n";
}

void write_row(std::ofstream& file, const char* experiment, std::size_t length, const char* mode,
               const char* work, std::size_t repeats, std::size_t uses, const char* opt, int trial,
               double seconds, unsigned long long result) {
    file << experiment << ',' << length << ',' << mode << ',' << work << ',' << repeats << ','
         << uses << ',' << opt << ',' << trial << ',' << seconds << ',' << result << '\n';
}

// ======================= Замеры опыта A =======================
// В каждой функции три одинаковых цикла, отличается только исследуемый вызов.
// Порядок входов и число вызовов у трёх способов одинаковые.
// guard складывает результаты, чтобы работа была нужна программе; он сохраняется после таймера.

double time_scalar(int pass, const unsigned int* samples, std::size_t repeats,
                   unsigned long long& guard) {
    guard = 0;
    auto start = std::chrono::steady_clock::now();
    if (pass == VALUE) {
        for (std::size_t r = 0; r < repeats; ++r) guard += scalar_value(samples[r % SAMPLES]);
    } else if (pass == REF) {
        for (std::size_t r = 0; r < repeats; ++r) guard += scalar_ref(samples[r % SAMPLES]);
    } else {
        for (std::size_t r = 0; r < repeats; ++r) guard += scalar_ptr(&samples[r % SAMPLES]);
    }
    auto finish = std::chrono::steady_clock::now();
    return seconds_between(start, finish);
}

double time_block_short(int pass, const Block* samples, std::size_t repeats,
                        unsigned long long& guard) {
    guard = 0;
    auto start = std::chrono::steady_clock::now();
    if (pass == VALUE) {
        for (std::size_t r = 0; r < repeats; ++r) guard += block_first_value(samples[r % SAMPLES]);
    } else if (pass == REF) {
        for (std::size_t r = 0; r < repeats; ++r) guard += block_first_ref(samples[r % SAMPLES]);
    } else {
        for (std::size_t r = 0; r < repeats; ++r) guard += block_first_ptr(&samples[r % SAMPLES]);
    }
    auto finish = std::chrono::steady_clock::now();
    return seconds_between(start, finish);
}

double time_block_full(int pass, const Block* samples, std::size_t repeats,
                       unsigned long long& guard) {
    guard = 0;
    auto start = std::chrono::steady_clock::now();
    if (pass == VALUE) {
        for (std::size_t r = 0; r < repeats; ++r) {
            Stats s = block_full_value(samples[r % SAMPLES]);
            guard += s.words + s.checksum;
        }
    } else if (pass == REF) {
        for (std::size_t r = 0; r < repeats; ++r) {
            Stats s = block_full_ref(samples[r % SAMPLES]);
            guard += s.words + s.checksum;
        }
    } else {
        for (std::size_t r = 0; r < repeats; ++r) {
            Stats s = block_full_ptr(&samples[r % SAMPLES]);
            guard += s.words + s.checksum;
        }
    }
    auto finish = std::chrono::steady_clock::now();
    return seconds_between(start, finish);
}

double time_text_short(int pass, const Text* samples, std::size_t repeats,
                       unsigned long long& guard) {
    guard = 0;
    auto start = std::chrono::steady_clock::now();
    if (pass == VALUE) {
        for (std::size_t r = 0; r < repeats; ++r) guard += text_first_value(samples[r % SAMPLES]);
    } else if (pass == REF) {
        for (std::size_t r = 0; r < repeats; ++r) guard += text_first_ref(samples[r % SAMPLES]);
    } else {
        for (std::size_t r = 0; r < repeats; ++r) guard += text_first_ptr(&samples[r % SAMPLES]);
    }
    auto finish = std::chrono::steady_clock::now();
    return seconds_between(start, finish);
}

double time_text_full(int pass, const Text* samples, std::size_t repeats,
                      unsigned long long& guard) {
    guard = 0;
    auto start = std::chrono::steady_clock::now();
    if (pass == VALUE) {
        for (std::size_t r = 0; r < repeats; ++r) {
            Stats s = text_full_value(samples[r % SAMPLES]);
            guard += s.words + s.checksum;
        }
    } else if (pass == REF) {
        for (std::size_t r = 0; r < repeats; ++r) {
            Stats s = text_full_ref(samples[r % SAMPLES]);
            guard += s.words + s.checksum;
        }
    } else {
        for (std::size_t r = 0; r < repeats; ++r) {
            Stats s = text_full_ptr(&samples[r % SAMPLES]);
            guard += s.words + s.checksum;
        }
    }
    auto finish = std::chrono::steady_clock::now();
    return seconds_between(start, finish);
}

// Число вызовов подобрано пробными запусками: самая быстрая серия идёт десятки миллисекунд.
const std::size_t SHORT_REPEATS = 20000000;

std::size_t full_repeats(std::size_t length) {
    if (length < 100) return 5000000;
    if (length < 5000) return 200000;
    return 10000;
}

// ======================= Скаляр =======================

int run_scalar(const char* opt) {
    unsigned int state = SEED;
    unsigned int samples[SAMPLES];
    for (std::size_t i = 0; i < SAMPLES; ++i) samples[i] = next_random(state) % 1000;

    for (std::size_t i = 0; i < SAMPLES; ++i) {
        if (scalar_value(samples[i]) != samples[i] + 1 || scalar_ref(samples[i]) != samples[i] + 1 ||
            scalar_ptr(&samples[i]) != samples[i] + 1) {
            std::cout << "Ошибка: скалярные варианты дают разные результаты\n";
            return 1;
        }
    }

    std::ofstream file(std::string("data/S_") + opt + ".csv");
    if (!file) return 1;
    write_header(file);

    for (int trial = 0; trial <= TRIALS; ++trial) {      // trial 0 - прогрев, в файл не идёт
        for (int j = 0; j < 3; ++j) {
            int pass = (trial + j) % 3;                    // порядок вариантов меняется
            unsigned long long guard = 0;
            double seconds = time_scalar(pass, samples, SHORT_REPEATS, guard);
            if (trial > 0) {
                write_row(file, "scalar", 0, PASS_NAMES[pass], "short", SHORT_REPEATS, 1, opt, trial,
                          seconds, guard);
            }
        }
    }
    std::cout << "скаляр готов, sizeof(unsigned int) = " << sizeof(unsigned int) << '\n';
    return 0;
}

// ======================= Опыт A =======================

int run_a(const char* opt) {
    const std::size_t length = BLOCK_SIZE - 1;   // полезная длина и для Block, и для Text
    unsigned int state = SEED;

    // Владелец блоков - массив blocks, владелец символов Text - массивы sources[i].
    // Всё живёт до конца функции и освобождается в её конце.
    Block* blocks = new Block[SAMPLES];
    for (std::size_t i = 0; i < SAMPLES; ++i) fill_block(blocks[i], state);

    char* sources[SAMPLES];
    Text texts[SAMPLES];
    for (std::size_t i = 0; i < SAMPLES; ++i) {
        sources[i] = make_text(length, state);
        texts[i] = Text{sources[i], length};
    }

    // Проверка до замеров: все способы передачи дают один результат на каждом входе.
    bool ok = true;
    for (std::size_t i = 0; i < SAMPLES; ++i) {
        Stats b = analyze({blocks[i].data, length});
        Stats v = block_full_value(blocks[i]);
        Stats r = block_full_ref(blocks[i]);
        Stats p = block_full_ptr(&blocks[i]);
        if (v.words != b.words || r.words != b.words || p.words != b.words) ok = false;
        if (v.checksum != b.checksum || r.checksum != b.checksum || p.checksum != b.checksum) ok = false;
        if (block_first_value(blocks[i]) != block_first_ref(blocks[i]) ||
            block_first_ref(blocks[i]) != block_first_ptr(&blocks[i])) ok = false;

        Stats t = analyze(texts[i]);
        v = text_full_value(texts[i]);
        r = text_full_ref(texts[i]);
        p = text_full_ptr(&texts[i]);
        if (v.words != t.words || r.words != t.words || p.words != t.words) ok = false;
        if (v.checksum != t.checksum || r.checksum != t.checksum || p.checksum != t.checksum) ok = false;
        if (text_first_value(texts[i]) != text_first_ref(texts[i]) ||
            text_first_ref(texts[i]) != text_first_ptr(&texts[i])) ok = false;
    }
    if (!ok) {
        std::cout << "Ошибка: способы передачи дают разные результаты\n";
        return 1;
    }

    std::ofstream file(std::string("data/A_") + opt + "_" + std::to_string(BLOCK_SIZE) + ".csv");
    if (!file) return 1;
    write_header(file);

    std::size_t repeats_full = full_repeats(length);

    for (int trial = 0; trial <= TRIALS; ++trial) {      // trial 0 - прогрев
        for (int j = 0; j < 3; ++j) {
            int pass = (trial + j) % 3;
            unsigned long long guard = 0;
            double seconds = 0.0;

            seconds = time_block_short(pass, blocks, SHORT_REPEATS, guard);
            if (trial > 0) write_row(file, "block", length, PASS_NAMES[pass], "short", SHORT_REPEATS,
                                     1, opt, trial, seconds, guard);

            seconds = time_block_full(pass, blocks, repeats_full, guard);
            if (trial > 0) write_row(file, "block", length, PASS_NAMES[pass], "full", repeats_full,
                                     1, opt, trial, seconds, guard);

            seconds = time_text_short(pass, texts, SHORT_REPEATS, guard);
            if (trial > 0) write_row(file, "text", length, PASS_NAMES[pass], "short", SHORT_REPEATS,
                                     1, opt, trial, seconds, guard);

            seconds = time_text_full(pass, texts, repeats_full, guard);
            if (trial > 0) write_row(file, "text", length, PASS_NAMES[pass], "full", repeats_full,
                                     1, opt, trial, seconds, guard);
        }
    }

    std::cout << "опыт A готов: длина " << length << ", sizeof(Block) = " << sizeof(Block)
              << ", sizeof(Text) = " << sizeof(Text) << '\n';

    for (std::size_t i = 0; i < SAMPLES; ++i) delete[] sources[i];
    delete[] blocks;
    return 0;
}

// ======================= Опыт B =======================
// Одна группа: одна строка длины L анализируется ровно K раз. Групп G, вход меняется по кругу.

unsigned long long run_borrow(const Text* texts, std::size_t groups, std::size_t uses) {
    unsigned long long guard = 0;
    for (std::size_t g = 0; g < groups; ++g) {
        Text source = texts[g % SAMPLES];
        for (std::size_t k = 0; k < uses; ++k) {
            Stats s = analyze(source);
            guard += s.words + s.checksum;
        }
    }
    return guard;
}

unsigned long long run_copy_each(const Text* texts, std::size_t groups, std::size_t uses) {
    unsigned long long guard = 0;
    for (std::size_t g = 0; g < groups; ++g) {
        Text source = texts[g % SAMPLES];
        for (std::size_t k = 0; k < uses; ++k) {
            char* copy = clone_text(source);                 // копия перед каждым анализом
            Stats s = analyze({copy, source.size});
            delete[] copy;                                   // и сразу освобождение
            guard += s.words + s.checksum;
        }
    }
    return guard;
}

unsigned long long run_copy_once(const Text* texts, std::size_t groups, std::size_t uses) {
    unsigned long long guard = 0;
    for (std::size_t g = 0; g < groups; ++g) {
        Text source = texts[g % SAMPLES];
        char* copy = clone_text(source);                     // одна копия на группу
        for (std::size_t k = 0; k < uses; ++k) {
            Stats s = analyze({copy, source.size});
            guard += s.words + s.checksum;
        }
        delete[] copy;
    }
    return guard;
}

// ---- Отдельный проход со счётчиками памяти (время здесь не измеряется) ----

struct Counters {
    unsigned long long allocations = 0;   // вызовов new[] для копий
    unsigned long long copied_bytes = 0;  // перенесено полезных байтов, без терминаторов
    unsigned long long current_extra = 0; // сейчас выделено char под копии, с терминаторами
    unsigned long long peak_extra = 0;    // максимум current_extra
};

// Счётчики меняются в момент настоящего выделения и освобождения.
char* counted_clone(Text text, Counters& c) {
    char* copy = clone_text(text);
    ++c.allocations;
    c.copied_bytes += text.size;
    c.current_extra += text.size + 1;
    if (c.current_extra > c.peak_extra) c.peak_extra = c.current_extra;
    return copy;
}

void counted_release(char* copy, std::size_t size, Counters& c) {
    delete[] copy;
    c.current_extra -= size + 1;
}

// Та же последовательность действий, что в замере. mode: 0 borrow, 1 copy_each, 2 copy_once.
unsigned long long count_mode(int mode, const Text* texts, std::size_t groups, std::size_t uses,
                              Counters& c) {
    unsigned long long guard = 0;
    for (std::size_t g = 0; g < groups; ++g) {
        Text source = texts[g % SAMPLES];
        if (mode == 0) {
            for (std::size_t k = 0; k < uses; ++k) {
                Stats s = analyze(source);
                guard += s.words + s.checksum;
            }
        } else if (mode == 1) {
            for (std::size_t k = 0; k < uses; ++k) {
                char* copy = counted_clone(source, c);
                Stats s = analyze({copy, source.size});
                counted_release(copy, source.size, c);
                guard += s.words + s.checksum;
            }
        } else {
            char* copy = counted_clone(source, c);
            for (std::size_t k = 0; k < uses; ++k) {
                Stats s = analyze({copy, source.size});
                guard += s.words + s.checksum;
            }
            counted_release(copy, source.size, c);
        }
    }
    return guard;
}

int run_b(const char* opt) {
    const std::size_t LENGTHS[3] = {15, 1023, 16383};
    const std::size_t USES[3] = {1, 10, 100};
    // Всего анализов G * K для каждой длины (подобрано пробным запуском).
    const std::size_t ANALYSES[3] = {4000000, 200000, 10000};
    const char* MODE_NAMES[3] = {"borrow", "copy_each", "copy_once"};

    std::ofstream times("data/B_times.csv");
    std::ofstream memory("data/B_memory.csv");
    if (!times || !memory) return 1;
    write_header(times);
    memory << "length,repeats,uses,mode,allocations,copied_bytes,peak_extra_bytes\n";

    unsigned int state = SEED;
    bool counters_match = true;

    for (int li = 0; li < 3; ++li) {
        std::size_t length = LENGTHS[li];

        // Исходные строки готовятся заранее и живут весь опыт. Владелец - массив sources.
        char* sources[SAMPLES];
        Text texts[SAMPLES];
        for (std::size_t i = 0; i < SAMPLES; ++i) {
            sources[i] = make_text(length, state);
            texts[i] = Text{sources[i], length};
        }

        for (int ki = 0; ki < 3; ++ki) {
            std::size_t uses = USES[ki];
            std::size_t groups = ANALYSES[li] / uses;

            // Проверка: три режима дают одну и ту же итоговую сумму.
            unsigned long long expected = run_borrow(texts, groups, uses);
            if (run_copy_each(texts, groups, uses) != expected ||
                run_copy_once(texts, groups, uses) != expected) {
                std::cout << "Ошибка: режимы дают разные результаты\n";
                return 1;
            }

            // Замеры времени (счётчики здесь не участвуют). Предыдущая проверка служит прогревом.
            for (int trial = 1; trial <= TRIALS; ++trial) {
                for (int j = 0; j < 3; ++j) {
                    int mode = (trial + j) % 3;
                    unsigned long long guard = 0;
                    auto start = std::chrono::steady_clock::now();
                    if (mode == 0) guard = run_borrow(texts, groups, uses);
                    else if (mode == 1) guard = run_copy_each(texts, groups, uses);
                    else guard = run_copy_once(texts, groups, uses);
                    auto finish = std::chrono::steady_clock::now();
                    write_row(times, "copy", length, MODE_NAMES[mode], "full", groups, uses, opt,
                              trial, seconds_between(start, finish), guard);
                }
            }

            // Отдельный проход со счётчиками и сравнение с прогнозом через L, K, G.
            for (int mode = 0; mode < 3; ++mode) {
                Counters c;
                unsigned long long guard = count_mode(mode, texts, groups, uses, c);

                unsigned long long want_alloc = 0, want_bytes = 0, want_peak = 0;
                if (mode == 1) {
                    want_alloc = groups * uses;
                    want_bytes = groups * uses * length;
                    want_peak = length + 1;
                } else if (mode == 2) {
                    want_alloc = groups;
                    want_bytes = groups * length;
                    want_peak = length + 1;
                }
                if (guard != expected || c.allocations != want_alloc || c.copied_bytes != want_bytes ||
                    c.peak_extra != want_peak || c.current_extra != 0) {
                    counters_match = false;
                }
                memory << length << ',' << groups << ',' << uses << ',' << MODE_NAMES[mode] << ','
                       << c.allocations << ',' << c.copied_bytes << ',' << c.peak_extra << '\n';
            }
        }

        for (std::size_t i = 0; i < SAMPLES; ++i) delete[] sources[i];
    }

    std::cout << "опыт B готов, счётчики "
              << (counters_match ? "совпали с прогнозом" : "НЕ совпали с прогнозом") << '\n';
    return counters_match ? 0 : 1;
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cout << "Запуск: ./research S|A|B O0|O2\n";
        return 1;
    }
    char experiment = argv[1][0];
    const char* opt = argv[2];

    if (experiment == 'S') return run_scalar(opt);
    if (experiment == 'A') return run_a(opt);
    if (experiment == 'B') return run_b(opt);

    std::cout << "Неизвестный опыт\n";
    return 1;
}
