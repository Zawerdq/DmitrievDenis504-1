#!/usr/bin/env python3
"""Сводные таблицы и графики по CSV из data/. Запуск: python3 plot.py"""
import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PLOTS = os.path.join(HERE, "plots")
os.makedirs(PLOTS, exist_ok=True)

MODES_A = ["value", "ref", "ptr"]
MODES_B = ["borrow", "copy_each", "copy_once"]
COLORS = {"value": "#d62728", "ref": "#1f77b4", "ptr": "#2ca02c",
          "borrow": "#1f77b4", "copy_each": "#d62728", "copy_once": "#ff7f0e"}


def q1(x):
    return x.quantile(0.25)


def q3(x):
    return x.quantile(0.75)


def summarize(df, keys, per):
    """Медиана и квартили времени на один вызов (нс). Условия не смешиваются: группировка по всем ключам."""
    df = df.copy()
    df["ns"] = df["seconds"] / df[per] * 1e9
    g = df.groupby(keys)["ns"]
    s = g.agg(["median", q1, q3, "min", "max", "count"]).reset_index()
    s["iqr_rel_%"] = (s["q3"] - s["q1"]) / s["median"] * 100
    return s


# ----------------------------------------------------------------------------- опыт A
a = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(DATA, "A_*.csv")))], ignore_index=True)
a["calls"] = a["repeats"] * a["uses"]
sa = summarize(a, ["experiment", "length", "work", "opt", "mode"], "calls")
sa.to_csv(os.path.join(DATA, "summary_A.csv"), index=False, float_format="%.4g")

fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True)
for i, work in enumerate(["short", "full"]):
    for j, opt in enumerate(["O0", "O2"]):
        ax = axes[i][j]
        for exp, ls, mk in [("Block", "-", "o"), ("Text", "--", "s")]:
            for m in MODES_A:
                d = sa[(sa.experiment == exp) & (sa.work == work) & (sa.opt == opt) & (sa["mode"] == m)]
                d = d.sort_values("length")
                ax.errorbar(d["length"], d["median"], yerr=[d["median"] - d["q1"], d["q3"] - d["median"]],
                            ls=ls, marker=mk, color=COLORS[m], capsize=3, label=f"{exp} {m}")
        sc = sa[(sa.experiment == "scalar") & (sa.opt == opt)]
        for m in MODES_A:
            v = sc[sc["mode"] == m]["median"]
            if len(v):
                ax.axhline(v.iloc[0], color=COLORS[m], ls=":", lw=1)
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_title(f"{'короткая' if work == 'short' else 'полная'} обработка, -{opt}")
        ax.set_xlabel("полезная длина текста, символов")
        ax.set_ylabel("время на вызов, нс (медиана, IQR)")
        ax.grid(True, which="both", alpha=0.3)
axes[0][0].legend(fontsize=8, ncol=2, title="точечные линии — unsigned int")
fig.suptitle("Опыт A: время одного вызова в зависимости от размера и способа передачи")
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "A_time_per_call.png"), dpi=130)
plt.close(fig)

# Относительная цена передачи: value / ref
piv = sa.pivot_table(index=["experiment", "length", "work", "opt"], columns="mode", values="median").reset_index()
piv["value/ref"] = piv["value"] / piv["ref"]
piv["ptr/ref"] = piv["ptr"] / piv["ref"]
piv.to_csv(os.path.join(DATA, "summary_A_ratios.csv"), index=False, float_format="%.4g")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
for j, opt in enumerate(["O0", "O2"]):
    ax = axes[j]
    for exp, ls in [("Block", "-"), ("Text", "--")]:
        for work, mk in [("short", "o"), ("full", "^")]:
            d = piv[(piv.experiment == exp) & (piv.work == work) & (piv.opt == opt)].sort_values("length")
            ax.plot(d["length"], d["value/ref"], ls=ls, marker=mk, label=f"{exp}, {work}")
    ax.axhline(1, color="gray", lw=1)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_title(f"-{opt}: во сколько раз передача по значению медленнее ссылки")
    ax.set_xlabel("полезная длина текста")
    ax.set_ylabel("медиана(value) / медиана(ref)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "A_value_vs_ref.png"), dpi=130)
plt.close(fig)

# ----------------------------------------------------------------------------- опыт B
b = pd.read_csv(os.path.join(DATA, "B_O2.csv"))
b["analyses"] = b["repeats"] * b["uses"]
sb = summarize(b, ["length", "uses", "mode"], "analyses")
sb.to_csv(os.path.join(DATA, "summary_B.csv"), index=False, float_format="%.4g")

lengths = sorted(sb["length"].unique())
fig, axes = plt.subplots(1, len(lengths), figsize=(14, 4.5))
for ax, L in zip(axes, lengths):
    for m in MODES_B:
        d = sb[(sb.length == L) & (sb["mode"] == m)].sort_values("uses")
        ax.errorbar(d["uses"], d["median"], yerr=[d["median"] - d["q1"], d["q3"] - d["median"]],
                    marker="o", color=COLORS[m], capsize=3, label=m)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title(f"L = {L}")
    ax.set_xlabel("K (анализов в группе)")
    ax.set_ylabel("время на один анализ, нс")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
fig.suptitle("Опыт B: seconds / (G·K), -O2")
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "B_time_per_analysis.png"), dpi=130)
plt.close(fig)

pb = sb.pivot_table(index=["length", "uses"], columns="mode", values="median").reset_index()
pb["copy_each/borrow"] = pb["copy_each"] / pb["borrow"]
pb["copy_once/borrow"] = pb["copy_once"] / pb["borrow"]
pb["copy_each/copy_once"] = pb["copy_each"] / pb["copy_once"]
pb["extra_each_ns"] = pb["copy_each"] - pb["borrow"]   # накладные на один анализ
pb["extra_once_ns"] = pb["copy_once"] - pb["borrow"]
pb.to_csv(os.path.join(DATA, "summary_B_ratios.csv"), index=False, float_format="%.4g")

# Счётчики памяти
c = pd.read_csv(os.path.join(DATA, "B_counters.csv"))
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
for ax, col, title in zip(axes, ["allocations", "copied_bytes", "peak_extra_bytes"],
                          ["вызовов new[]", "скопировано полезных байтов", "пик доп. буферов, байт"]):
    for m in ["copy_each", "copy_once"]:
        for L, mk in zip(lengths, ["o", "s", "^"]):
            d = c[(c.length == L) & (c["mode"] == m)].sort_values("uses")
            ax.plot(d["uses"], d[col] / (d["repeats"] if col != "peak_extra_bytes" else 1), marker=mk,
                    color=COLORS[m], ls="-" if m == "copy_each" else "--", label=f"{m}, L={L}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("K")
    ax.set_title(title + (" на группу" if col != "peak_extra_bytes" else ""))
    ax.grid(True, which="both", alpha=0.3)
axes[0].legend(fontsize=7)
fig.suptitle("Опыт B: учёт дополнительной памяти (borrow — все нули, не показан на лог-шкале)")
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "B_memory_counters.png"), dpi=130)
plt.close(fig)

print("summary_A.csv, summary_B.csv и графики в plots/ обновлены")
