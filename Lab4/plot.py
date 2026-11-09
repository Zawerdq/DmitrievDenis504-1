# Сводные таблицы (медиана и разброс) и графики по CSV из папки data.
# Запуск: python3 plot.py
import csv
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read(name):
    with open(name, newline="") as f:
        return list(csv.DictReader(f))


def group(rows, key_fields):
    groups = {}
    for r in rows:
        groups.setdefault(tuple(r[k] for k in key_fields), []).append(float(r["seconds"]))
    return groups


def save_summary(name, key_fields, groups):
    with open(name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(key_fields + ["trials", "median_s", "min_s", "max_s"])
        for key, v in groups.items():
            w.writerow(list(key) + [len(v), f"{statistics.median(v):.6g}", f"{min(v):.6g}", f"{max(v):.6g}"])


def errorbar(ax, xs, series, **kw):
    """Точка - медиана, отрезок - от минимума до максимума."""
    med = [statistics.median(v) for v in series]
    ax.errorbar(xs, med, yerr=[[m - min(v) for m, v in zip(med, series)],
                               [max(v) - m for m, v in zip(med, series)]], capsize=3, **kw)


# ---------------- 1. capacity от size ----------------
cap = read("data/capacity.csv")
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
styles = {"std::vector": ("-", 3.0), "subvector x2": ("--", 1.5), "subvector x1.5": (":", 1.5)}
for name, (style, width) in styles.items():
    pts = [(int(r["size"]), int(r["capacity"])) for r in cap if r["container"] == name]
    xs = [p[0] for p in pts] + [10_000_000]
    ys = [p[1] for p in pts] + [pts[-1][1]]
    axes[0].step(xs, ys, where="post", linestyle=style, linewidth=width, label=name)
    axes[1].step(xs, ys, where="post", linestyle=style, linewidth=width, label=name)
axes[0].set_xlim(0, 300)
axes[0].set_ylim(0, 550)
axes[0].set_title("Первые 300 элементов")
axes[1].set_xscale("log")
axes[1].set_yscale("log")
axes[1].set_xlim(1, 10_000_000)
axes[1].set_title("До 10 миллионов, логарифмические оси")
for ax in axes:
    ax.set_xlabel("size")
    ax.set_ylabel("capacity")
    ax.grid(True, alpha=0.3)
    ax.legend()
fig.suptitle("Зависимость capacity от size при последовательных push_back")
fig.tight_layout()
fig.savefig("plots/capacity.png", dpi=130)
plt.close(fig)

# ---------------- 2. Сравнение стратегий ----------------
names = ["+10", "+100", "x1.5", "x2", "std::vector"]
markers = {"+10": "o", "+100": "s", "x1.5": "^", "x2": "v", "std::vector": "D"}
st = group(read("data/strategies.csv"), ["strategy", "n"])
save_summary("data/summary_strategies.csv", ["strategy", "n"], st)

small = list(range(100_000, 1_000_001, 100_000))
fig, ax = plt.subplots(figsize=(8, 5))
for name in names:
    errorbar(ax, small, [st[(name, str(n))] for n in small], marker=markers[name], label=name)
ax.set_yscale("log")
ax.set_xlabel("Число добавленных элементов n")
ax.set_ylabel("Время заполнения, с")
ax.set_title("Все стратегии, n от 100 тысяч до 1 миллиона")
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig("plots/strategies_small.png", dpi=130)
plt.close(fig)

large = list(range(1_000_000, 10_000_001, 1_000_000))
fig, ax = plt.subplots(figsize=(8, 5))
for name in ["x1.5", "x2", "std::vector"]:
    errorbar(ax, [n / 1e6 for n in large], [[t * 1000 for t in st[(name, str(n))]] for n in large],
             marker=markers[name], label=name)
ax.set_xlabel("Число добавленных элементов n, млн")
ax.set_ylabel("Время заполнения, мс")
ax.set_ylim(bottom=0)
ax.set_title("Умножающие стратегии и std::vector, n от 1 до 10 миллионов")
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig("plots/strategies_large.png", dpi=130)
plt.close(fig)

# ---------------- 3. Время от множителя ----------------
fa = group(read("data/factor.csv"), ["factor", "n"])
save_summary("data/summary_factor.csv", ["factor", "n"], fa)
fc = {(r["factor"], r["n"]): r for r in read("data/factor_counts.csv")}
factors = sorted({k[0] for k in fa}, key=float)
ns = sorted({k[1] for k in fa}, key=int)
fx = [float(f) for f in factors]

fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
for n, marker in zip(ns, ["o", "s", "^"]):
    label = f"n = {int(n) // 1_000_000} млн"
    errorbar(axes[0], fx, [[t / int(n) * 1e9 for t in fa[(f, n)]] for f in factors], marker=marker, label=label)
    axes[1].plot(fx, [int(fc[(f, n)]["copied_elements"]) / int(n) for f in factors], marker=marker, label=label)
    axes[2].plot(fx, [int(fc[(f, n)]["final_capacity"]) / int(n) for f in factors], marker=marker, label=label)
axes[1].plot(fx, [1 / (k - 1) for k in fx], "k--", linewidth=1, label="границы: 1/(k-1) и k/(k-1)")
axes[1].plot(fx, [k / (k - 1) for k in fx], "k--", linewidth=1)
axes[2].plot(fx, [1 for k in fx], "k--", linewidth=1, label="границы: 1 и k")
axes[2].plot(fx, fx, "k--", linewidth=1)
axes[0].set_ylabel("Время на один элемент, нс")
axes[0].set_title("Время заполнения")
axes[1].set_ylabel("Перенесено элементов / n")
axes[1].set_title("Работа по переносу")
axes[2].set_ylabel("Итоговая capacity / n")
axes[2].set_title("Запас памяти")
for ax in axes:
    ax.set_xlabel("Множитель k")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend()
fig.suptitle("Стратегия capacity = capacity * k: время, перенос элементов и память")
fig.tight_layout()
fig.savefig("plots/factor.png", dpi=130)
plt.close(fig)

# ---------------- 4. Время от слагаемого ----------------
sp = group(read("data/step.csv"), ["step", "n"])
save_summary("data/summary_step.csv", ["step", "n"], sp)
sc = {r["step"]: r for r in read("data/step_counts.csv")}
steps = sorted({k[0] for k in sp}, key=float)
n = int(next(iter(sp))[1])
sx = [float(s) for s in steps]

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
errorbar(axes[0], sx, [sp[(s, str(n))] for s in steps], marker="o", label="измерение")
base = statistics.median(sp[("100", str(n))])
axes[0].plot(sx, [base * 100 / s for s in sx], "k--", linewidth=1, label="время ~ 1/c (через точку c = 100)")
axes[0].set_ylabel("Время заполнения, с")
axes[0].set_title("Время заполнения")
axes[1].plot(sx, [int(sc[s]["copied_elements"]) / n for s in steps], marker="o", label="подсчёт")
axes[1].plot(sx, [n / (2 * s) for s in sx], "k--", linewidth=1, label="формула n / (2c)")
axes[1].set_ylabel("Перенесено элементов / n")
axes[1].set_title("Работа по переносу")
for ax in axes:
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Слагаемое c")
    ax.grid(True, alpha=0.3)
    ax.legend()
fig.suptitle(f"Стратегия capacity = capacity + c, n = {n // 1_000_000} млн элементов")
fig.tight_layout()
fig.savefig("plots/step.png", dpi=130)
plt.close(fig)

print("Готово: data/summary_*.csv, plots/*.png")
