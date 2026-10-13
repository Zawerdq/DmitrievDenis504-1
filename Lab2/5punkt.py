import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

CSV_FILE = Path(__file__).with_name("pi_time.csv")
df = pd.read_csv(CSV_FILE)

names = {
    1: "Leibniz",
    2: "Nilakantha",
    3: "Wallis",
    4: "Basel"
}

# Оставляем только случаи, где нужная точность реально достигнута
df = df[df["iterations"] != -1]


# =========================================================
# 1. ЧИСЛО ИТЕРАЦИЙ
# =========================================================

plt.figure(figsize=(10, 6))

for method in sorted(df["method"].unique()):
    part = df[df["method"] == method]

    plt.plot(
        part["eps"],
        part["iterations"],
        marker="o",
        label=names[method]
    )

plt.xscale("log")
plt.yscale("log")
plt.gca().invert_xaxis()

plt.xlabel("Required accuracy")
plt.ylabel("Number of iterations")
plt.title("Iterations required to reach accuracy")

plt.grid(True)
plt.legend()
plt.tight_layout()


# =========================================================
# 2. ВРЕМЯ
# =========================================================

plt.figure(figsize=(10, 6))

for method in sorted(df["method"].unique()):
    part = df[df["method"] == method]

    plt.plot(
        part["eps"],
        part["time"],
        marker="o",
        label=names[method]
    )

plt.xscale("log")
plt.yscale("log")
plt.gca().invert_xaxis()

plt.xlabel("Required accuracy")
plt.ylabel("Execution time, s")
plt.title("Time required to reach accuracy")

plt.grid(True)
plt.legend()
plt.tight_layout()


# показываем оба окна одновременно
plt.show()