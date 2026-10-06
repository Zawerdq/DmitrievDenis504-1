#include "sortirovki.hpp"
#include <chrono>
#include <iostream>
#include <random>

int rand_uns(int min, int max) {
    static std::default_random_engine generator(12345);
    std::uniform_int_distribution<int> raspredelenie(min, max);
    return raspredelenie(generator);
}

int main() {
    int punkt;
    std::cout << "0 - Tri prostye sortirovki\n"
              << "1 - Puzyrkovaya s tekushchey optimizaciey\n"
              << "2 - Tri bystrye sortirovki\n"
              << "3 - Vse shest sortirovok\n"
              << "4 - Sluchaynyy, pryamoy i obratnyy poryadok\n"
              << "Punkt: ";
    if (!(std::cin >> punkt) || punkt < 0 || punkt > 4) return 1;

    int malye[] = {500, 1000, 2000, 4000, 8000};
    int obshchie[] = {1000, 2000, 4000, 8000, 16000};
    int bolshie[] = {10000, 20000, 40000, 80000, 160000};
    const char* nazvaniya[] = {
        "Puzyrkovaya", "Vstavkami", "Vyborom",
        "Bystraya", "Sliyaniem", "Piramidalnaya"
    };
    const char* poryadok[] = {"Sluchaynyy", "Pryamoy", "Obratnyy"};

    for (int k = 0; k < 5; ++k) {
        int n = obshchie[k];
        if (punkt == 0 || punkt == 1) n = malye[k];
        if (punkt == 2) n = bolshie[k];
        int vidov = 1;
        if (punkt == 4) vidov = 3;

        int* ishodnyy = new int[n];
        int* massiv = new int[n];

        for (int vid = 0; vid < vidov; ++vid) {
            for (int i = 0; i < n; ++i) ishodnyy[i] = i;
            if (vid == 0) {
                for (int i = n - 1; i > 0; --i) {
                    int j = rand_uns(0, i);
                    swap(ishodnyy[i], ishodnyy[j]);
                }
            }
            if (vid == 2) {
                for (int i = 0; i < n; ++i) ishodnyy[i] = n - 1 - i;
            }

            std::cout << "\nn = " << n << ", " << poryadok[vid] << '\n';
            for (int nomer = 0; nomer < 6; ++nomer) {
                if (punkt == 0 && nomer > 2) continue;
                if (punkt == 1 && nomer != 0) continue;
                if (punkt == 2 && nomer < 3) continue;

                double vremya = 0;
                for (int povtor = 0; povtor < 3; ++povtor) {
                    for (int i = 0; i < n; ++i) massiv[i] = ishodnyy[i];

                    auto nachalo = std::chrono::steady_clock::now();
                    if (nomer == 0) bubble_sort(massiv, n);
                    else if (nomer == 1) insertion_sort(massiv, n);
                    else if (nomer == 2) selection_sort(massiv, n);
                    else if (nomer == 3) quick_sort(massiv, 0, n - 1);
                    else if (nomer == 4) merge_sort(massiv, 0, n - 1);
                    else heap_sort(massiv, n);
                    auto konec = std::chrono::steady_clock::now();
                    vremya += std::chrono::duration<double>(konec - nachalo).count();

                    for (int i = 0; i < n; ++i) {
                        if (massiv[i] != i) {
                            std::cout << "Oshibka sortirovki: " << nazvaniya[nomer] << '\n';
                            delete[] ishodnyy;
                            delete[] massiv;
                            return 1;
                        }
                    }
                }
                std::cout << nazvaniya[nomer] << ": " << vremya / 3 << " s\n";
            }
        }
        delete[] ishodnyy;
        delete[] massiv;
    }
    return 0;
}
