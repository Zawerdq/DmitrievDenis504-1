# Сводные таблицы (медиана и разброс) и графики по CSV из папки data.
# Запуск: python3 plot.py
import csv
import glob
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PASSES = ["value", "ref", "ptr"]
PASS_LABELS = {"value": "по значению", "ref": "по ссылке", "ptr": "по указателю"}
MODES = ["borrow", "copy_each", "copy_once"]
MARKERS = {"value": "o", "ref": "s", "ptr": "^", "borrow": "o", "copy_each": "s", "copy_once": "^"}


def read_rows(pattern):
    rows = []
    for name in sorted(glob.glob(pattern)):
        with open(name, newline="") as f:
            rows += list(csv.DictReader(f))
    return rows


def group_ns(rows, key_fields):
    """Сгруппировать замеры по условию опыта; время перевести в наносекунды на один вызов."""
    groups = {}
    for r in rows:
        key = tuple(r[k] for k in key_fields)
        calls = int(r["repeats"]) * int(r["uses"])
        groups.setdefault(key, []).append(float(r["seconds"]) / calls * 1e9)
    return groups


def save_summary(name, key_fields, groups):
    with open(name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(key_fields + ["trials", "median_ns", "min_ns", "max_ns"])
        for key, values in groups.items():
            w.writerow(list(key) + [len(values), f"{statistics.median(values):.4g}",
                                    f"{min(values):.4g}", f"{max(values):.4g}"])


# ---------------- Опыт A и скаляр ----------------
a_fields = ["experiment", "length", "work", "opt", "mode"]
a = group_ns(read_rows("data/A_*.csv") + read_rows("data/S_*.csv"), a_fields)
save_summary("data/summary_A.csv", a_fields, a)

lengths = [15, 1023, 16383]
for work, title in [("short", "короткая работа (первый байт)"), ("full", "полный проход")]:
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5))
    for row, experiment in enumerate(["block", "text"]):
        for col, opt in enumerate(["O0", "O2"]):
            ax = axes[row][col]
            for mode in PASSES:
                med = [statistics.median(a[(experiment, str(n), work, opt, mode)]) for n in lengths]
                low = [min(a[(experiment, str(n), work, opt, mode)]) for n in lengths]
                high = [max(a[(experiment, str(n), work, opt, mode)]) for n in lengths]
                ax.errorbar(lengths, med,
                            yerr=[[m - l for m, l in zip(med, low)], [h - m for m, h in zip(med, high)]],
                            marker=MARKERS[mode], capsize=3, label=PASS_LABELS[mode])
            ax.set_xscale("log")
            panel = [statistics.median(a[(experiment, str(n), work, opt, m)])
                     for n in lengths for m in PASSES]
            if max(panel) / min(panel) > 10:
                ax.set_yscale("log")      # времена различаются на порядки
            else:
                ax.set_ylim(bottom=0)     # времена близки: обычная шкала от нуля
            ax.set_xticks(lengths)
            ax.set_xticklabels([str(n) for n in lengths])
            ax.minorticks_off()
            ax.set_xticks(lengths)
            ax.set_xticklabels([str(n) for n in lengths])
            ax.grid(True, alpha=0.3)
            ax.set_title(("Block" if experiment == "block" else "Text") + ", сборка -" + opt)
            if row == 1:
                ax.set_xlabel("Полезная длина, символов")
            if col == 0:
                ax.set_ylabel("Время на один вызов, нс")
    axes[0][0].legend()
    fig.suptitle("Опыт A: " + title + ". Точка - медиана, отрезок - от минимума до максимума")
    fig.tight_layout()
    fig.savefig(f"plots/A_{work}.png", dpi=130)
    plt.close(fig)

# ---------------- Опыт B: время ----------------
b_fields = ["length", "uses", "mode"]
b = group_ns(read_rows("data/B_times.csv"), b_fields)
save_summary("data/summary_B.csv", b_fields, b)

uses = [1, 10, 100]
fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
for ax, n in zip(axes, lengths):
    for mode in MODES:
        med = [statistics.median(b[(str(n), str(k), mode)]) for k in uses]
        low = [min(b[(str(n), str(k), mode)]) for k in uses]
        high = [max(b[(str(n), str(k), mode)]) for k in uses]
        ax.errorbar(uses, med,
                    yerr=[[m - l for m, l in zip(med, low)], [h - m for m, h in zip(med, high)]],
                    marker=MARKERS[mode], capsize=3, label=mode)
    ax.set_xscale("log")
    ax.set_xticks(uses)
    ax.set_xticklabels([str(k) for k in uses])
    ax.minorticks_off()
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.set_title(f"L = {n}")
    ax.set_xlabel("K - число анализов одной строки")
axes[0].set_ylabel("Время на один анализ, нс")
axes[0].legend()
fig.suptitle("Опыт B (-O2): время на один анализ, seconds / (G * K)")
fig.tight_layout()
fig.savefig("plots/B_time.png", dpi=130)
plt.close(fig)

# ---------------- Опыт B: счётчики памяти ----------------
with open("data/B_memory.csv", newline="") as f:
    mem = list(csv.DictReader(f))

fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
panels = [("allocations", "Вызовов new[]"), ("copied_bytes", "Скопировано полезных байтов"),
          ("peak_extra_bytes", "Пик дополнительной памяти, char")]
for ax, (field, title) in zip(axes, panels):
    for mode in ["copy_each", "copy_once"]:          # у borrow все счётчики равны нулю
        for n in lengths:
            ys = [int(r[field]) for k in uses for r in mem
                  if r["mode"] == mode and int(r["length"]) == n and int(r["uses"]) == k]
            ax.plot(uses, ys, marker=MARKERS[mode], linestyle="-" if mode == "copy_each" else "--",
                    label=f"{mode}, L={n}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(uses)
    ax.set_xticklabels([str(k) for k in uses])
    ax.minorticks_off()
    ax.grid(True, alpha=0.3)
    ax.set_title(title)
    ax.set_xlabel("K")
axes[0].legend(fontsize=7)
fig.suptitle("Опыт B: счётчики памяти (borrow не показан: везде 0)")
fig.tight_layout()
fig.savefig("plots/B_memory.png", dpi=130)
plt.close(fig)

print("Готово: data/summary_A.csv, data/summary_B.csv, plots/*.png")
