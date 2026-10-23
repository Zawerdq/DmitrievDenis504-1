#!/usr/bin/env python3
"""Печатает markdown-таблицы для отчёта из data/summary_*.csv. Запуск: python3 tables.py"""
import os

import pandas as pd

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def fmt(x):
    if x >= 1000:
        return f"{x / 1000:.2f} мкс"
    return f"{x:.2f} нс"


a = pd.read_csv(os.path.join(D, "summary_A.csv"))
print("### A: медиана времени на вызов (в скобках — IQR, % от медианы)\n")
for work in ["short", "full"]:
    print(f"\n**{work}**\n")
    print("| объект | длина | сборка | value | ref | ptr | value/ref |")
    print("|---|---:|---|---:|---:|---:|---:|")
    for exp in ["scalar", "Block", "Text"]:
        for L in sorted(a[a.experiment == exp]["length"].unique()):
            for opt in ["O0", "O2"]:
                d = a[(a.experiment == exp) & (a.length == L) & (a.work == work) & (a.opt == opt)]
                if d.empty:
                    continue
                m = {r["mode"]: r for _, r in d.iterrows()}
                cells = [f"{fmt(m[k]['median'])} ({m[k]['iqr_rel_%']:.0f}%)" for k in ["value", "ref", "ptr"]]
                print(f"| {exp} | {L} | -{opt} | " + " | ".join(cells) +
                      f" | {m['value']['median'] / m['ref']['median']:.2f} |")

b = pd.read_csv(os.path.join(D, "summary_B.csv"))
print("\n### B: время на один анализ, медиана (IQR %)\n")
print("| L | K | borrow | copy_each | copy_once | copy_each/borrow | copy_once/borrow | (copy_each−borrow), нс |")
print("|---:|---:|---:|---:|---:|---:|---:|---:|")
for L in sorted(b.length.unique()):
    for K in sorted(b.uses.unique()):
        d = b[(b.length == L) & (b.uses == K)]
        m = {r["mode"]: r for _, r in d.iterrows()}
        cells = [f"{fmt(m[k]['median'])} ({m[k]['iqr_rel_%']:.0f}%)" for k in ["borrow", "copy_each", "copy_once"]]
        print(f"| {L} | {K} | " + " | ".join(cells) +
              f" | {m['copy_each']['median'] / m['borrow']['median']:.2f}"
              f" | {m['copy_once']['median'] / m['borrow']['median']:.2f}"
              f" | {m['copy_each']['median'] - m['borrow']['median']:.1f} |")
