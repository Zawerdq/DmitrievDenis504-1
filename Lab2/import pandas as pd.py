import pandas as pd
import matplotlib.pyplot as plt
import math
from pathlib import Path

CSV_FILE = Path(__file__).with_name("pi.csv")
df = pd.read_csv(CSV_FILE)

formulas = ["Leibniz", "Nilakantha", "Wallis", "Basel"]
PI = math.pi


# =========================================================
# 1. Общий график сходимости
# =========================================================

plt.figure(figsize=(11, 7))

for formula in formulas:
    plt.plot(df["n"], df[formula], label=formula)

plt.axhline(PI, linestyle="--", linewidth=2, label="True pi")

plt.xscale("log")

plt.xlabel("Number of iterations")
plt.ylabel("Calculated value of pi")
plt.title("Convergence of iterative formulas for pi")

plt.grid(True)
plt.legend()
plt.tight_layout()

plt.savefig(
    Path(__file__).with_name("pi_convergence.png"),
    dpi=200
)


# =========================================================
# 2. Увеличение около pi
# =========================================================

plt.figure(figsize=(11, 7))

for formula in formulas:
    plt.plot(df["n"], df[formula], label=formula)

plt.axhline(PI, linestyle="--", linewidth=2, label="True pi")

plt.xscale("log")
plt.ylim(3.13, 3.15)

plt.xlabel("Number of iterations")
plt.ylabel("Calculated value of pi")
plt.title("Convergence near the true value of pi")

plt.grid(True)
plt.legend()
plt.tight_layout()

plt.savefig(
    Path(__file__).with_name("pi_zoom.png"),
    dpi=200
)


# =========================================================
# 3. Абсолютная ошибка
# =========================================================

plt.figure(figsize=(11, 7))

for formula in formulas:
    error = abs(df[formula] - PI)

    # Нули нельзя показывать на логарифмической оси
    error = error.where(error > 0)

    plt.plot(df["n"], error, label=formula)

plt.xscale("log")
plt.yscale("log")

plt.xlabel("Number of iterations")
plt.ylabel("Absolute error |pi_N - pi|")
plt.title("Absolute error of iterative formulas for pi")

plt.grid(True)
plt.legend()
plt.tight_layout()

plt.savefig(
    Path(__file__).with_name("pi_error.png"),
    dpi=200
)


# =========================================================
# Показываем ВСЕ окна одновременно
# =========================================================

plt.show()