#!/usr/bin/env python3
"""Графики и сводные таблицы по data/*.csv. Запуск: python3 plot.py"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PLOTS = os.path.join(HERE, "plots")
os.makedirs(PLOTS, exist_ok=True)


def ok(df):
    return df[df["status"] == "ok"].copy()


def summarize(df, keys):
    g = df.groupby(keys)
    s = g.agg(median=("seconds", "median"), q1=("seconds", lambda x: x.quantile(0.25)),
              q3=("seconds", lambda x: x.quantile(0.75)), trials=("seconds", "count"),
              reallocations=("reallocations", "first"), moved_elements=("moved_elements", "first"),
              peak_elements=("peak_elements", "first"), final_capacity=("final_capacity", "first")).reset_index()
    s["ns_per_elem"] = s["median"] / s["n"] * 1e9
    s["final_cap/n"] = s["final_capacity"] / s["n"]
    s["peak/n"] = s["peak_elements"] / s["n"]
    s["moved/n"] = s["moved_elements"] / s["n"]
    return s


# ------------------------------------------------------------ 1. capacity std::vector
cap = pd.read_csv(os.path.join(DATA, "std_capacity.csv"))
changes = cap[cap["capacity"].diff().fillna(1) != 0].copy()
changes["ratio"] = changes["capacity"] / changes["capacity"].shift(1)
changes.to_csv(os.path.join(DATA, "std_capacity_changes.csv"), index=False)

fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
small = cap[cap["size"] <= 200]
axes[0].step(small["size"], small["capacity"], where="post", label="capacity")
axes[0].plot(small["size"], small["size"], "--", color="gray", label="size")
axes[0].set_xlabel("size")
axes[0].set_ylabel("capacity")
axes[0].set_title("std::vector<int>: size ≤ 200")
axes[0].legend()
axes[0].grid(alpha=0.3)
axes[1].step(cap["size"], cap["capacity"], where="post", label="capacity")
axes[1].plot(cap["size"], cap["size"], "--", color="gray", label="size")
axes[1].set_xscale("log", base=2)
axes[1].set_yscale("log", base=2)
axes[1].set_xlabel("size")
axes[1].set_ylabel("capacity")
axes[1].set_title("std::vector<int>: до 2·10⁶ элементов (лог. оси)")
axes[1].legend()
axes[1].grid(alpha=0.3, which="both")
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "std_capacity.png"), dpi=130)
plt.close(fig)

# ------------------------------------------------------------ 2. стратегии
st = pd.read_csv(os.path.join(DATA, "strategies.csv"))
ss = summarize(ok(st), ["strategy", "n"])
ss.to_csv(os.path.join(DATA, "summary_strategies.csv"), index=False, float_format="%.4g")
order = ["std::vector", "std::vector+reserve", "x2", "x1.5", "+100", "+10"]
colors = {"std::vector": "black", "std::vector+reserve": "gray", "x2": "#1f77b4", "x1.5": "#2ca02c",
          "+100": "#ff7f0e", "+10": "#d62728"}
styles = {"std::vector": "--", "std::vector+reserve": ":"}

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for s in order:
    d = ss[ss.strategy == s].sort_values("n")
    for ax in axes:
        ax.errorbar(d["n"] / 1e6, d["median"], yerr=[d["median"] - d["q1"], d["q3"] - d["median"]],
                    marker="o", ms=3, color=colors[s], ls=styles.get(s, "-"), capsize=2, label=s)
axes[0].set_yscale("log")
axes[0].set_title("Время заполнения (лог. шкала), все стратегии")
axes[1].set_ylim(0, ss[ss.strategy.isin(["std::vector", "x2", "x1.5"])]["median"].max() * 1.3)
axes[1].set_xlim(0, 10.5)
axes[1].set_title("То же, линейная шкала (+10, +100 уходят вверх)")
for ax in axes:
    ax.set_xlabel("n, млн элементов")
    ax.set_ylabel("время, с (медиана, IQR)")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "strategies_time.png"), dpi=130)
plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 5))
for s in order:
    d = ss[ss.strategy == s].sort_values("n")
    ax.plot(d["n"] / 1e6, d["ns_per_elem"], marker="o", ms=3, color=colors[s], ls=styles.get(s, "-"), label=s)
ax.set_yscale("log")
ax.set_xlabel("n, млн элементов")
ax.set_ylabel("нс на один push_back (медиана)")
ax.set_title("Амортизированная цена push_back")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "strategies_per_element.png"), dpi=130)
plt.close(fig)

# ------------------------------------------------------------ 3. множитель
fa = pd.read_csv(os.path.join(DATA, "factor.csv"))
fs = summarize(ok(fa), ["param", "n"]).sort_values(["param", "n"])
fs.to_csv(os.path.join(DATA, "summary_factor.csv"), index=False, float_format="%.4g")
# усреднение по разным n одного множителя (условие опыта — множитель; n — разные точки одного условия)
fm = fs.groupby("param").agg(ns_mean=("ns_per_elem", "mean"), ns_min=("ns_per_elem", "min"),
                             ns_max=("ns_per_elem", "max"), cap_mean=("final_cap/n", "mean"),
                             cap_max=("final_cap/n", "max"), peak_mean=("peak/n", "mean"),
                             peak_max=("peak/n", "max"), moved_mean=("moved/n", "mean"),
                             realloc_10M=("reallocations", "last")).reset_index()
fm.to_csv(os.path.join(DATA, "summary_factor_mean.csv"), index=False, float_format="%.4g")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
ax = axes[0]
for n, c in zip(sorted(fs["n"].unique()), plt.cm.viridis([0.1, 0.3, 0.5, 0.7, 0.9])):
    d = fs[fs.n == n]
    ax.plot(d["param"], d["ns_per_elem"], "o-", ms=3, lw=0.8, color=c, alpha=0.6, label=f"n = {n / 1e6:g} млн")
ax.errorbar(fm["param"], fm["ns_mean"], yerr=[fm["ns_mean"] - fm["ns_min"], fm["ns_max"] - fm["ns_mean"]],
            color="black", marker="s", lw=2, capsize=3, label="среднее по n (min–max)")
ax.set_xscale("log", base=2)
ax.set_yscale("log")
ax.set_xlabel("множитель роста capacity (лог. шкала)")
ax.set_ylabel("нс на один push_back (медиана замеров)")
ax.set_title("Время заполнения от множителя")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8)
ax = axes[1]
ax.plot(fm["param"], fm["cap_mean"], "s-", color="#d62728", label="capacity / n в конце (среднее)")
ax.plot(fm["param"], fm["cap_max"], "s:", color="#d62728", alpha=0.5, label="capacity / n (худший из n)")
ax.plot(fm["param"], fm["peak_mean"], "^-", color="#9467bd", label="пик старый+новый буфер / n (среднее)")
ax.plot(fm["param"], fm["moved_mean"], "o-", color="#2ca02c", label="перенесено элементов / n")
ax.set_xscale("log", base=2)
ax.set_yscale("log")
ax.set_xlabel("множитель роста capacity (лог. шкала)")
ax.set_ylabel("в единицах n")
ax.set_title("Цена по памяти и копированиям")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "factor.png"), dpi=130)
plt.close(fig)

# ------------------------------------------------------------ 4. прибавляемая константа
sp = pd.read_csv(os.path.join(DATA, "step.csv"))
sps = summarize(ok(sp), ["param", "n"]).sort_values(["n", "param"])
sps.to_csv(os.path.join(DATA, "summary_step.csv"), index=False, float_format="%.4g")
fig, ax = plt.subplots(figsize=(9, 5))
for n, c in [(1000000, "#2ca02c"), (10000000, "#d62728")]:
    d = sps[sps.n == n]
    ax.errorbar(d["param"], d["median"], yerr=[d["median"] - d["q1"], d["q3"] - d["median"]], marker="o",
                capsize=3, color=c, label=f"n = {n:,}".replace(",", " "))
    # теоретическая асимптота ~ n^2 / step, привязанная к самой медленной измеренной точке
    if len(d):
        ref = d.iloc[0]
        xs = d["param"]
        ax.plot(xs, ref["median"] * ref["param"] / xs, ":", color=c, lw=1, label=f"∝ 1/step, n={n:.0e}")
mul2 = ss[(ss.strategy == "x2") & (ss.n == 10000000)]["median"]
if len(mul2):
    ax.axhline(mul2.iloc[0], color="#1f77b4", ls="--", lw=1, label="x2 при n = 10⁷")
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("прибавляемая константа step (лог. шкала)")
ax.set_ylabel("время заполнения, с")
ax.set_title("Аддитивный рост: время от константы")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS, "step.png"), dpi=130)
plt.close(fig)

print("plots/ и сводные таблицы обновлены")
