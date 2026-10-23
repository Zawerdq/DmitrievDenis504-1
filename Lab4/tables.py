#!/usr/bin/env python3
"""Markdown-таблицы для REPORT.md из data/summary_*.csv. Запуск: python3 tables.py"""
import os

import pandas as pd

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def t(sec):
    if sec >= 1:
        return f"{sec:.2f} с"
    return f"{sec * 1000:.2f} мс"


s = pd.read_csv(os.path.join(D, "summary_strategies.csv"))
order = ["std::vector", "std::vector+reserve", "x2", "x1.5", "+100", "+10"]
print("<!--TABLE_STRAT-->")
print("| n | " + " | ".join(order) + " |")
print("|---:|" + "---:|" * len(order))
for n in [100000, 500000, 1000000, 2000000, 5000000, 10000000]:
    row = []
    for st in order:
        d = s[(s.strategy == st) & (s.n == n)]
        row.append(t(d["median"].iloc[0]) if len(d) else "пропущено")
    print(f"| {n:,} | ".replace(",", " ") + " | ".join(row) + " |")
print()
print("| стратегия | перевыделений при n=10⁶ | перенесено / n при n=10⁶ | capacity / n при n=10⁶ |")
print("|---|---:|---:|---:|")
for st in order:
    d = s[(s.strategy == st) & (s.n == 1000000)]
    if len(d):
        r = d.iloc[0]
        print(f"| {st} | {int(r.reallocations)} | {r['moved/n']:.3g} | {r['final_cap/n']:.3g} |")

f = pd.read_csv(os.path.join(D, "summary_factor_mean.csv"))
print("\n<!--TABLE_FACTOR-->")
print("| k | нс/элемент, среднее по 5 n (min–max) | перенесено / n | 1/(k−1) | capacity / n (среднее / худшее) | перевыделений при n=10⁷ |")
print("|---:|---:|---:|---:|---:|---:|")
for _, r in f.iterrows():
    k = r["param"]
    print(f"| {k:g} | {r.ns_mean:.2f} ({r.ns_min:.2f}–{r.ns_max:.2f}) | {r.moved_mean:.2f} | {1 / (k - 1):.2f} | "
          f"{r.cap_mean:.2f} / {r.cap_max:.2f} | {int(r.realloc_10M)} |")

p = pd.read_csv(os.path.join(D, "summary_step.csv"))
print("\n<!--TABLE_STEP-->")
print("| step | n = 10⁶ | n = 10⁷ |")
print("|---:|---:|---:|")
for st in sorted(p["param"].unique()):
    cells = []
    for n in [1000000, 10000000]:
        d = p[(p.param == st) & (p.n == n)]
        cells.append(t(d["median"].iloc[0]) + f" ({int(d.reallocations.iloc[0])} перевыд.)" if len(d) else "пропущено (> 20 с)")
    print(f"| {st:,} | ".replace(",", " ") + " | ".join(cells) + " |")
