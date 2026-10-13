import pandas as pd
import matplotlib.pyplot as plt
import math
from pathlib import Path

CSV_FILE = Path(__file__).with_name("polygon_pi.csv")

df = pd.read_csv(CSV_FILE)

# =========================================================
# Само приближение
# =========================================================

plt.figure(figsize=(11, 7))

plt.plot(
    df["N"],
    df["pi_polygon"],
    marker="o",
    label="Polygon"
)

plt.axhline(
    math.pi,
    linestyle="--",
    label="True pi"
)

plt.xscale("log", base=2)

plt.xlabel("Number of polygon sides N")
plt.ylabel("Calculated value of pi")
plt.title("Numerical instability of polygon approximation")

plt.grid(True)
plt.legend()
plt.tight_layout()


# =========================================================
# Ошибка
# =========================================================

plt.figure(figsize=(11, 7))

error = abs(df["pi_polygon"] - math.pi)

plt.plot(
    df["N"],
    error,
    marker="o",
    label="Polygon error"
)

plt.xscale("log", base=2)
plt.yscale("log")

plt.xlabel("Number of polygon sides N")
plt.ylabel("Absolute error")
plt.title("Error of polygon approximation")

plt.grid(True)
plt.legend()
plt.tight_layout()

plt.show()