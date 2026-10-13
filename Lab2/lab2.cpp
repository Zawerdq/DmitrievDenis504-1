#include <iostream>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <chrono>
int pi_iterations(int method, float eps) {
    const double PI = 3.141592653589793;

    float value;

    if (method == 1) value = 0.0f;  // Leibniz
    if (method == 2) value = 3.0f;  // Nilakantha
    if (method == 3) value = 1.0f;  // Wallis product
    if (method == 4) value = 0.0f;  // Basel sum

    for (int n = 1; n <= 10000000; n++) {

        float pi;

        if (method == 1) {
            int k = n - 1;

            if (k % 2 == 0)
                value += 4.0f / (2.0f * k + 1.0f);
            else
                value -= 4.0f / (2.0f * k + 1.0f);

            pi = value;
        }

        else if (method == 2) {
            float x = 2.0f * n;

            if (n % 2 == 1)
                value += 4.0f / (x * (x + 1) * (x + 2));
            else
                value -= 4.0f / (x * (x + 1) * (x + 2));

            pi = value;
        }

        else if (method == 3) {
            float x = n;

            value *= (4.0f * x * x) /
                     (4.0f * x * x - 1.0f);

            pi = 2.0f * value;
        }

        else {
            float x = n;

            value += 1.0f / (x * x);

            pi = std::sqrt(6.0f * value);
        }

        if (std::fabs(pi - PI) < eps)
            return n;
    }

    return -1;
}
int pow(int a, int n){
    if (n==0){
        return(1);
    }
    int b=a;
    for(int i=1;i<n;i++){
        a=a*b;
    }
    return(a);
}
union FloatView {
float f;
unsigned int u;
};
void binarnye(unsigned int n){
    int longility=sizeof(n)*8;
    for(int k=longility-1;k>=0;k--){
        std::cout << ((n>>k)&1);
    }
}
int main(){
std::cout << "Punkt: 1) Vtoroy-1. Tretey -2" << std::endl;
int a;
std::cin >> a;
if (a==1){
    FloatView v;
    v.f=1.0f;
    std::cout << std::fixed;
    std::cout.precision(2);
    for(int i=0;i<15;i++){
        v.f*=10.0f;
        std::cout << v.f << "   ";
        binarnye(v.u);
        std::cout << '\n';
    }
}
else if (a==2){
    float x = 0.0f;
    while (true) {
        float next = x + 1.0f;

        if (next == x) {
             std::cout << "\nx Izmeneneya otsutstvuyet: " << x << std::endl;
            break;
    }

    x = next;
}
}
else if (a == 3){
    std::ofstream file("pi.csv");

    file << "n,Leibniz,Nilakantha,Wallis,Basel\n";

    float leibniz = 0.0f;
    float nilakantha = 3.0f;
    float wallis_product = 1.0f;
    float basel_sum = 0.0f;

    const int N = 100000;

    for(int n = 1; n <= N; n++){

        int k = n - 1;

        if(k % 2 == 0){
            leibniz += 4.0f / (2.0f * k + 1.0f);
        }
        else{
            leibniz -= 4.0f / (2.0f * k + 1.0f);
        }


        float x = 2.0f * n;

        if(n % 2 == 1){
            nilakantha += 4.0f / (x * (x + 1.0f) * (x + 2.0f));
        }
        else{
            nilakantha -= 4.0f / (x * (x + 1.0f) * (x + 2.0f));
        }

        float nf = static_cast<float>(n);

        wallis_product *=
            (4.0f * nf * nf) /
            (4.0f * nf * nf - 1.0f);

        float wallis = 2.0f * wallis_product;

        basel_sum += 1.0f / (nf * nf);

        float basel = std::sqrt(6.0f * basel_sum);
        if(n <= 100 || n % 100 == 0){
            file << n << ","
                 << leibniz << ","
                 << nilakantha << ","
                 << wallis << ","
                 << basel << "\n";
        }
    }

    file.close();

    std::cout << "Dannye zapisany v pi.csv\n";
}
else if (a == 4){
    std::ofstream file("polygon_pi.csv");
    file << std::setprecision(9);

    file << "step,N,pi_polygon\n";

    float side = std::sqrt(2.0f);
    unsigned long long N = 4;

    for(int step = 0; step < 40; step++){

        float pi_polygon = N * side / 2.0f;

        file << step << ","
             << N << ","
             << pi_polygon << "\n";

        std::cout << "N = " << N
                  << "   pi = " << std::setprecision(9)
                  << pi_polygon << '\n';

        side = std::sqrt(
            2.0f - std::sqrt(4.0f - side * side)
        );

        N *= 2;

        if(side == 0.0f){
            std::cout << "side became zero\n";
            break;
        }
    }

    file.close();
}
else if (a == 5) {

    std::ofstream file("pi_time.csv");

    file << "method,eps,iterations,time\n";

    const int repeats = 100;

    for (int method = 1; method <= 4; method++) {

        for (int power = 1; power <= 10; power++) {

            float eps = std::pow(10.0f, -power);

            // Сначала узнаём, достигается ли вообще такая точность
            int iterations = pi_iterations(method, eps);

            // Если точность недостижима, не запускаем ещё 100 раз
            if (iterations == -1) {

                file << method << ","
                     << eps << ","
                     << -1 << ","
                     << -1 << "\n";

                std::cout
                    << "method = " << method
                    << "   eps = 1e-" << power
                    << "   NOT REACHED\n";

                continue;
            }

            // Измеряем суммарное время 100 запусков
            auto start = std::chrono::steady_clock::now();

            for (int r = 0; r < repeats; r++) {
                pi_iterations(method, eps);
            }

            auto end = std::chrono::steady_clock::now();

            double total_time =
                std::chrono::duration<double>(end - start).count();

            double average_time = total_time / repeats;

            file << method << ","
                 << eps << ","
                 << iterations << ","
                 << average_time << "\n";

            std::cout
                << "method = " << method
                << "   eps = 1e-" << power
                << "   iterations = " << iterations
                << "   average time = " << average_time
                << " s\n";
        }
    }

    file.close();

    std::cout << "\nDannye zapisany v pi_time.csv\n";
}
}