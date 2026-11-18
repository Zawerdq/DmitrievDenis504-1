// Демонстрация (Claude): множитель 1e300 -> static_cast<unsigned>(ceil(cap*f)) вне диапазона = UB.
// g++ -std=c++17 -fsanitize=undefined,float-cast-overflow ub_factor.cpp && ./a.out
#include "subvector.hpp"
int main(){ subvector v(1e300); for(int i=0;i<3;i++) if(!v.push_back(i)) return 7; return 0; }
