from pathlib import Path
from time import perf_counter
import subprocess
import sys
import matplotlib.pyplot as plt


def vstavkami(massiv):
    for i in range(1, len(massiv)):
        for j in range(i, 0, -1):
            if massiv[j] < massiv[j - 1]:
                massiv[j], massiv[j - 1] = massiv[j - 1], massiv[j]
            else:
                break


def vyborom(massiv):
    for i in range(len(massiv) - 1):
        nomer_minimuma = i
        for j in range(i + 1, len(massiv)):
            if massiv[j] < massiv[nomer_minimuma]:
                nomer_minimuma = j
        massiv[i], massiv[nomer_minimuma] = massiv[nomer_minimuma], massiv[i]


papka = Path(__file__).resolve().parent
programma = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else papka / "sortirovki.exe"
rezultat = subprocess.run([str(programma)], input="4\n", text=True,
                         capture_output=True, check=True, cwd=papka)
razmery = [1000, 2000, 4000, 8000, 16000]
cpp = {"Vstavkami": [], "Vyborom": []}
python = {"Vstavkami": [], "Vyborom": []}
obratnyy = False
for stroka in rezultat.stdout.splitlines():
    if stroka.startswith("n = "):
        obratnyy = "Obratnyy" in stroka
    elif obratnyy:
        for imya in cpp:
            if stroka.startswith(imya + ":"):
                cpp[imya].append(float(stroka.split()[1]))

for imya in cpp:
    if len(cpp[imya]) != len(razmery):
        raise ValueError("Нужна программа, собранная из main.cpp для пунктов 0–4")

for n in razmery:
    ishodnyy = list(range(n - 1, -1, -1))
    ozhidaemyy = list(range(n))
    for imya, sortirovka in [("Vstavkami", vstavkami), ("Vyborom", vyborom)]:
        vremya = 0
        for povtor in range(3):
            massiv = ishodnyy.copy()
            nachalo = perf_counter()
            sortirovka(massiv)
            vremya += perf_counter() - nachalo
            assert massiv == ozhidaemyy
        python[imya].append(vremya / 3)
        vremya_cpp = cpp[imya][len(python[imya]) - 1]
        print(f"n = {n}, {imya}: C++ = {vremya_cpp:.6f} s, "
              f"Python = {vremya / 3:.6f} s",
              flush=True)

figura, osi = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
for os, imya, nazvanie in zip(osi, cpp, ["Сортировка вставками", "Сортировка выбором"]):
    os.plot([n / 1000 for n in razmery], cpp[imya], "o-", label="C++ — " + nazvanie.lower(), linewidth=2)
    os.plot([n / 1000 for n in razmery], python[imya], "o-", label="Python — " + nazvanie.lower(), linewidth=2)
    os.set(title=nazvanie, xlabel="Размер массива N, тыс. элементов", ylabel="Время, с")
    os.set_ylim(bottom=0)
    os.set_xticks([n / 1000 for n in razmery])
    os.grid(alpha=0.3)
    os.legend()
figura.suptitle("C++ и Python: обратный порядок, среднее по трём запускам")
figura.savefig(papka / "grafiki" / "cpp_python_comparison.png", dpi=180)
plt.close(figura)
