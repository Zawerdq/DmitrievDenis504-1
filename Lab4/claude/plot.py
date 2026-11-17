"""Графики решения Claude: читает data/*.csv, пишет plots/*.png и data/summary.json (числа для отчёта)."""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
D, P = HERE / "data", HERE / "plots"
P.mkdir(exist_ok=True)
PHI = (1 + 5 ** 0.5) / 2
plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 100,
                     "axes.spines.top": False, "axes.spines.right": False})
COL = {"+10": "#d62728", "+100": "#ff7f0e", "x1.5": "#2ca02c", "x2": "#1f77b4",
       "std::vector": "#9467bd", "std::vector+reserve": "#7f7f7f"}
summary = {}


def read(name, delim=","):
    with open(D / name, newline="") as f:
        return list(csv.DictReader(f, delimiter=delim))


def save(fig, name):
    fig.savefig(P / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


def med_err(groups):
    m = [median(g) for g in groups]
    return m, [[a - min(g) for a, g in zip(m, groups)], [max(g) - a for a, g in zip(m, groups)]]


# ---------------------------------------------------------------- 01 capacity
def cap_series(name):
    rows = read(name)
    return [(int(r["size"]), int(r["capacity"])) for r in rows]


fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
series = {"libstdc++ (GCC)": cap_series("capacity_libstdcxx.csv")}
if (D / "capacity_libcxx.csv").exists():
    series["libc++ (Clang)"] = cap_series("capacity_libcxx.csv")
# MSVC STL: новая ёмкость = old + old/2 (целочисленно), но не меньше нужной (исходник <vector>, _Calculate_growth)
msvc, cap = [(0, 0)], 0
for size in range(1, 20_000_001):
    if size > cap:
        cap = max(cap + cap // 2, size)
        msvc.append((size, cap))
series["MSVC STL (по исходнику)"] = msvc
styles = ["-", "--", ":"]
for (name, pts), st in zip(series.items(), styles):
    xs = [p[0] for p in pts] + [20_000_000]
    ys = [p[1] for p in pts] + [pts[-1][1]]
    axes[0].step(xs, ys, where="post", ls=st, lw=2, label=name)
    axes[1].step(xs, ys, where="post", ls=st, lw=2, label=name)
axes[0].plot([0, 140], [0, 140], color="gray", lw=0.8, label="capacity = size")
axes[0].set(xlim=(0, 140), ylim=(0, 270), xlabel="size", ylabel="capacity", title="Первые 140 push_back")
axes[1].set(xscale="log", yscale="log", xlim=(1, 2e7), xlabel="size", ylabel="capacity", title="До 20 млн, лог. оси")
for ax in axes:
    ax.legend(fontsize=8)
fig.suptitle("01. Как растёт capacity у трёх стандартных библиотек")
save(fig, "01_capacity_three_stl.png")
summary["capacity_libstdcxx"] = [c for _, c in series["libstdc++ (GCC)"]][:12]
summary["capacity_msvc"] = [c for _, c in msvc][:14]
summary["reallocs_20M"] = {k: len(v) - 1 for k, v in series.items()}

# ---------------------------------------------------------------- 02/03/04 strategies
st = defaultdict(list)
fl = defaultdict(list)
for r in read("strategies.csv"):
    st[(r["strategy"], int(r["n"]))].append(float(r["seconds"]))
    fl[(r["strategy"], int(r["n"]))].append(int(r["minflt"]))
names = ["+10", "+100", "x1.5", "x2", "std::vector", "std::vector+reserve"]
ns_small = list(range(100_000, 1_000_001, 100_000))

fig, ax = plt.subplots(figsize=(8.5, 5))
fit = {}
for name in names:
    xs = [n for n in sorted({k[1] for k in st if k[0] == name}) if n <= 3_000_000]
    m, e = med_err([st[(name, n)] for n in xs])
    ax.errorbar(xs, m, yerr=e, marker="o", ms=3, capsize=2, color=COL[name], label=name)
    if name in ("+10", "+100"):
        # МНК для T = a n^2 по точкам n >= 300k
        pts = [(n, t) for n, t in zip(xs, m) if n >= 300_000]
        a = sum(t * n * n for n, t in pts) / sum(n ** 4 for n, _ in pts)
        fit[name] = a
        xx = [n for n in range(100_000, 10_000_001, 100_000)]
        ax.plot(xx, [a * n * n for n in xx], ls=":", color=COL[name], lw=1)
ax.set(xscale="log", yscale="log", xlabel="n (число push_back)", ylabel="время заполнения, с",
       title="02. Все стратегии: прибавление квадратично, умножение линейно")
ax.text(2.2e6, fit["+10"] * 4.84e12 * 4, f"+10: {fit['+10']*1e12:.1f}·(n/1млн)² с", color=COL["+10"], fontsize=8, ha="center")
ax.text(2.2e6, fit["+100"] * 4.84e12 * 4, f"+100: {fit['+100']*1e12:.2f}·(n/1млн)² с", color=COL["+100"], fontsize=8, ha="center")
ax.legend(fontsize=8)
save(fig, "02_strategies_loglog.png")
summary["fit_add"] = {k: v * 1e12 for k, v in fit.items()}
summary["extrapolate_10M"] = {k: v * 1e14 for k, v in fit.items()}
summary["strategies_table"] = {}
for n in [100_000, 500_000, 1_000_000, 3_000_000, 5_000_000, 10_000_000, 20_000_000]:
    summary["strategies_table"][n] = {name: (median(st[(name, n)]) if (name, n) in st else None) for name in names}

fig, axes = plt.subplots(2, 1, figsize=(9, 7.5), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
for name in ["x1.5", "x2", "std::vector", "std::vector+reserve"]:
    xs = sorted(n for (s, n) in st if s == name and n >= 1_000_000)
    m, e = med_err([[t / n * 1e9 for t in st[(name, n)]] for n in xs])
    axes[0].errorbar([x / 1e6 for x in xs], m, yerr=e, marker="o", ms=3, capsize=2, color=COL[name], label=name)
    axes[1].plot([x / 1e6 for x in xs], [median(fl[(name, n)]) / n * 1024 for n in xs], marker="o", ms=3,
                 color=COL[name], label=name)
for p in range(20, 25):
    for ax in axes:
        ax.axvline(2 ** p / 1e6, color=COL["x2"], lw=0.7, ls="--", alpha=0.6)
c = 0
caps15 = []
while c < 2e7:
    c = max(math.ceil(c * 1.5), c + 1)
    caps15.append(c)
for c in caps15:
    if c > 1e6:
        for ax in axes:
            ax.axvline(c / 1e6, color=COL["x1.5"], lw=0.7, ls=":", alpha=0.8)
axes[0].set(ylabel="нс на один push_back", title="03. Умножающие стратегии: «пила» на моментах перевыделения")
axes[1].set(xlabel="n, млн (вертикали — моменты перевыделения: синие ×2, зелёные ×1.5)",
            ylabel="page faults на 1024 эл.")
axes[0].set_ylim(bottom=0)
axes[1].set_ylim(bottom=0)
axes[0].set_xlim(0, 20.5)
axes[0].legend(fontsize=8)
save(fig, "03_multiplicative_sawtooth.png")

# Разложение времени на 10 млн, 20 млн
summary["ns_per_elem"] = {name: {n: median(st[(name, n)]) / n * 1e9 for n in [1_000_000, 5_000_000, 8_000_000, 8_500_000, 10_000_000, 16_500_000, 20_000_000] if (name, n) in st}
                          for name in ["x1.5", "x2", "std::vector", "std::vector+reserve"]}
summary["faults_per_1024"] = {name: {n: median(fl[(name, n)]) / n * 1024 for n in [1_000_000, 8_000_000, 8_500_000, 10_000_000, 20_000_000] if (name, n) in fl}
                              for name in ["x1.5", "x2", "std::vector", "std::vector+reserve"]}


# ---------------------------------------------------------------- 04 разложение времени (регрессия)
import numpy as np


def copies_mul(n, k):
    cap, c = 0, 0
    while cap < n:
        c += cap
        cap = max(math.ceil(cap * k) if cap else 1, cap + 1)
    return c


regr = {}
rows = []
for (name, n), ts in st.items():
    if name in ("x2", "x1.5", "std::vector", "std::vector+reserve") and n >= 1_000_000:
        k = {"x2": 2, "x1.5": 1.5, "std::vector": 2}.get(name)
        cp = copies_mul(n, k) if k else 0
        for t, f in zip(ts, fl[(name, n)]):
            rows.append((name, n, cp, f, t))
for grp, label in [(("x2", "x1.5"), "subvector"), (("std::vector", "std::vector+reserve"), "std::vector")]:
    R = [r for r in rows if r[0] in grp]
    A = np.array([[r[1], r[2], r[3]] for r in R], float)
    b = np.array([r[4] for r in R])
    coef, *_ = np.linalg.lstsq(A, b, rcond=None)
    pred = A @ coef
    regr[label] = {"ns_push": coef[0] * 1e9, "ns_copy": coef[1] * 1e9, "us_fault": coef[2] * 1e6,
                   "r2": float(1 - ((b - pred) ** 2).sum() / ((b - b.mean()) ** 2).sum())}
summary["regression"] = regr
fig, ax = plt.subplots(figsize=(9, 4.6))
cases = [("x2", 5_000_000), ("x2", 10_000_000), ("x2", 20_000_000), ("x1.5", 10_000_000), ("x1.5", 20_000_000),
         ("std::vector", 10_000_000), ("std::vector+reserve", 10_000_000), ("std::vector+reserve", 20_000_000)]
co = regr["subvector"]
labels = []
parts = {"push_back (запись)": [], "перенос элементов": [], "page faults": []}
meas = []
for name, n in cases:
    c = regr["std::vector"] if name.startswith("std") else co
    k = {"x2": 2, "x1.5": 1.5, "std::vector": 2}.get(name)
    cp = copies_mul(n, k) if k else 0
    f = median(fl[(name, n)])
    parts["push_back (запись)"].append(n * c["ns_push"] / 1e6)
    parts["перенос элементов"].append(cp * c["ns_copy"] / 1e6)
    parts["page faults"].append(f * c["us_fault"] / 1e3)
    meas.append(median(st[(name, n)]) * 1e3)
    labels.append(f"{name.replace('+reserve', chr(10) + '+reserve')}\n{n // 1_000_000} млн")
bottom = [0] * len(cases)
for (lab, vals), col in zip(parts.items(), ["#9ecae1", "#3182bd", "#e6550d"]):
    ax.bar(range(len(cases)), vals, bottom=bottom, color=col, label=lab)
    bottom = [a + b for a, b in zip(bottom, vals)]
ax.scatter(range(len(cases)), meas, color="k", zorder=3, label="измерено (медиана)")
ax.set_xticks(range(len(cases)), labels, fontsize=7)
ax.set(ylabel="мс", title=(f"04. Из чего состоит время: ≈{co['ns_push']:.1f} нс/push, {co['ns_copy']:.1f} нс/перенос, "
                           f"{co['us_fault']:.1f} мкс/page fault (R²={co['r2']:.2f})"))
ax.legend(fontsize=8)
save(fig, "04_time_decomposition.png")

# ---------------------------------------------------------------- 05 realloc
re = defaultdict(list)
for r in read("realloc.csv"):
    re[(r["strategy"], r["how"], int(r["n"]))].append(float(r["seconds"]))
hows = ["new+loop", "new+memcpy", "realloc"]
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
for s, mk in zip(["+10", "+100", "x2"], ["o", "s", "^"]):
    for h, ls in zip(hows, ["-", "--", ":"]):
        xs = sorted(n for (a, b, n) in re if a == s and b == h)
        m, _ = med_err([re[(s, h, n)] for n in xs])
        axes[0].plot([x / 1e3 for x in xs], [t * 1e3 for t in m], marker=mk, ls=ls, ms=4,
                     color=COL[s], label=f"{s}, {h}")
axes[0].set(yscale="log", xlabel="n, тыс.", ylabel="время, мс", title="Время заполнения")
axes[0].legend(fontsize=7, ncol=3)
mv = read("realloc_moves.csv")
labels, vals, cols = [], [], []
for r in mv:
    if r["n"] == "1000000":
        labels.append(f"{r['strategy']}\n{r['how'].replace('new+', '')}")
        vals.append(int(r["moved_elements"]) / 1e6)
        cols.append(COL[r["strategy"]])
axes[1].bar(range(len(vals)), [max(v, 1e-3) for v in vals], color=cols)
axes[1].set_xticks(range(len(vals)), labels, fontsize=7)
axes[1].set(yscale="log", ylabel="перенесено элементов, млн (n = 1 млн)",
            title="Сколько элементов реально переехало")
for i, v in enumerate(vals):
    axes[1].text(i, max(v, 1e-3) * 1.3, f"{v:,.1f}".replace(",", " ") if v >= 0.1 else f"{v*1e6:.0f} шт.",
                 ha="center", fontsize=7)
fig.suptitle("05. Почему у Codex «+10» быстрый: realloc почти не переносит данные")
save(fig, "05_realloc_vs_copy.png")
summary["realloc_500k_ms"] = {f"{s} {h}": median(re[(s, h, 500_000)]) * 1e3 for s in ["+10", "+100", "x2"] for h in hows}
summary["realloc_moves"] = [{k: r[k] for k in r} for r in mv]

# ---------------------------------------------------------------- 06 factor
fa = defaultdict(list)
fcap, fcop = {}, {}
for r in read("factor.csv"):
    k, n = float(r["factor"]), int(r["n"])
    fa[(k, n)].append(float(r["seconds"]) / n * 1e9)
    fcap[(k, n)] = int(r["final_capacity"]) / n
    fcop[(k, n)] = int(r["copied"]) / n
ks = sorted({k for k, _ in fa})
nsf = sorted({n for _, n in fa})
fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
t_mean = [sum(median(fa[(k, n)]) for n in nsf) / len(nsf) for k in ks]
t_lo = [min(median(fa[(k, n)]) for n in nsf) for k in ks]
t_hi = [max(median(fa[(k, n)]) for n in nsf) for k in ks]
axes[0].fill_between(ks, t_lo, t_hi, alpha=0.2, color="#1f77b4", label="мин–макс по 37 значениям n")
axes[0].plot(ks, t_mean, "o-", ms=3, color="#1f77b4", label="среднее по n")
axes[0].set(xlabel="множитель k", ylabel="нс на push_back", title="Время (усреднено по n от 1 до 10 млн)")
c_mean = [sum(fcop[(k, n)] for n in nsf) / len(nsf) for k in ks]
axes[1].plot(ks, c_mean, "o-", ms=3, label="среднее по n (точно)")
axes[1].plot(ks, [1 / (k - 1) for k in ks], "k--", lw=1, label="1/(k−1) и k/(k−1)")
axes[1].plot(ks, [k / (k - 1) for k in ks], "k--", lw=1)
axes[1].set(xlabel="множитель k", ylabel="перенесено / n", title="Работа по переносу", ylim=(0, 12))
o_mean = [sum(fcap[(k, n)] - 1 for n in nsf) / len(nsf) * 100 for k in ks]
o_max = [max(fcap[(k, n)] - 1 for n in nsf) * 100 for k in ks]
axes[2].plot(ks, o_mean, "o-", ms=3, label="средний запас")
axes[2].plot(ks, o_max, "s-", ms=3, label="худший запас")
axes[2].plot(ks, [(k - 1) * 100 for k in ks], "k--", lw=1, label="предел (k−1)·100 %")
axes[2].plot(ks, [((k - 1) / math.log(k) - 1) * 100 for k in ks], "k:", lw=1, label="теория среднего (k−1)/ln k − 1")
axes[2].set(xlabel="множитель k", ylabel="неиспользуемая память, % от n", title="Запас памяти")
for ax in axes:
    ax.axvline(PHI, color="goldenrod", lw=1)
    ax.legend(fontsize=7)
axes[0].text(PHI, axes[0].get_ylim()[1] * 0.95, " φ≈1.618", color="goldenrod", fontsize=8, va="top")
axes[0].set_ylim(bottom=0)
fig.suptitle("06. Выбор множителя: плотная развёртка 32 k × 37 n × 3 повтора")
save(fig, "06_factor_sweep.png")
summary["factor"] = {f"{k:.3f}": {"ns": t, "copied": c, "over_mean": o, "over_max": om}
                     for k, t, c, o, om in zip(ks, t_mean, c_mean, o_mean, o_max)}

# ---------------------------------------------------------------- 07 step
sp = defaultdict(list)
for r in read("step.csv"):
    sp[(int(r["step"]), int(r["n"]))].append(float(r["seconds"]))
fig, axes = plt.subplots(1, 3, figsize=(16, 4.3))
for n, mk in [(250_000, "o"), (500_000, "s")]:
    cs = sorted(c for c, nn in sp if nn == n)
    m, e = med_err([sp[(c, n)] for c in cs])
    axes[0].errorbar(cs, m, yerr=e, marker=mk, ms=4, capsize=2, label=f"n = {n//1000} тыс.")
    axes[1].plot(cs, [t * c for t, c in zip(m, cs)], marker=mk, ms=4, label=f"n = {n//1000} тыс.")
    axes[0].plot(cs, [n * n / (2 * c) * 0.65e-9 + n * 1.2e-9 for c in cs], "k:", lw=1)
axes[0].set(xscale="log", yscale="log", xlabel="слагаемое c", ylabel="время, с",
            title="Время; пунктир: n²/(2c)·0.65 нс + n·1.2 нс")
axes[1].set(xscale="log", yscale="log", xlabel="слагаемое c", ylabel="время × c, с",
            title="T·c ≈ const, пока доминирует перенос")
for ax in axes:
    ax.legend(fontsize=8)
spf = defaultdict(list)
spff = defaultdict(list)
spd = defaultdict(list)
for r in read("step_fixed_threshold.csv"):
    spf[(int(r["step"]), int(r["n"]))].append(float(r["seconds"]))
    spff[(int(r["step"]), int(r["n"]))].append(int(r["minflt"]))
for r in read("step.csv"):
    spd[(int(r["step"]), int(r["n"]))].append(int(r["minflt"]))
n = 500_000
cs = sorted(c for c, nn in sp if nn == n)
axes[2].plot(cs, [median(sp[(c, n)]) for c in cs], "o-", label="порог mmap динамический (по умолчанию)")
axes[2].plot(cs, [median(spf[(c, n)]) for c in cs], "s--", label="порог зафиксирован 32 МБ (GLIBC_TUNABLES)")
ax2 = axes[2].twinx()
ax2.plot(cs, [max(median(spd[(c, n)]), 1) for c in cs], "o:", color="gray", lw=0.8)
ax2.plot(cs, [max(median(spff[(c, n)]), 1) for c in cs], "s:", color="#d62728", lw=0.8)
ax2.set(yscale="log", ylabel="page faults (пунктир)")
axes[2].set(xscale="log", yscale="log", xlabel="слагаемое c", ylabel="время, с", title="n = 500 тыс.: два режима malloc")
axes[2].legend(fontsize=7, loc="lower left")
summary["step_modes"] = {c: [median(sp[(c, n)]), median(spf[(c, n)]), median(spd[(c, n)]), median(spff[(c, n)])] for c in cs}
fig.suptitle("07. Стратегия capacity += c")
save(fig, "07_step_sweep.png")
summary["step"] = {f"{c},{n}": median(v) for (c, n), v in sp.items()}

# ---------------------------------------------------------------- 08 latency
lat = defaultdict(list)
for r in read("latency.csv"):
    lat[r["strategy"]].append((int(r["index"]), int(r["cycles"])))
fig, ax = plt.subplots(figsize=(9, 4.5))
for name, col in [("x2", COL["x2"]), ("x1.5", COL["x1.5"]), ("+100000", "#8c564b")]:
    pts = lat[name]
    ax.scatter([p[0] / 1e6 for p in pts], [p[1] / 2.1e3 for p in pts], s=10, color=col, label=name, alpha=0.8)
ax.set(yscale="log", xlabel="номер push_back, млн", ylabel="время одного push_back, мкс (только > 5 мкс)",
       title="08. Отдельный push_back: обычно ~15 нс, при перевыделении — миллисекунды")
ax.legend()
save(fig, "08_latency_spikes.png")
summary["latency"] = read("latency_summary.csv")

# ---------------------------------------------------------------- 09 types
ty = defaultdict(list)
for r in read("types.csv"):
    ty[(r["type"], int(r["n"]))].append(float(r["seconds"]))
fig, ax = plt.subplots(figsize=(8, 4.5))
for name, col in [("move noexcept", "#2ca02c"), ("move без noexcept", "#d62728"), ("только копия", "#ff7f0e"),
                  ("reserve(n)", "#7f7f7f")]:
    xs = sorted(n for t, n in ty if t == name)
    m, e = med_err([[t / n * 1e9 for t in ty[(name, n)]] for n in xs])
    ax.errorbar([x / 1e6 for x in xs], m, yerr=e, marker="o", capsize=2, color=col, label=name)
ax.set(xlabel="n, млн", ylabel="нс на emplace_back", ylim=(0, None),
       title="09. std::vector<объект со строкой>: без noexcept вектор копирует, а не перемещает")
ax.legend(fontsize=8)
save(fig, "09_noexcept_move.png")
summary["types"] = {f"{t},{n}": median(v) for (t, n), v in ty.items()}

# ---------------------------------------------------------------- 10 implementations
if (D / "compare.csv").exists():
    cm = defaultdict(list)
    for r in read("compare.csv"):
        cm[(r["implementation"], r["mode"], int(r["n"]))].append(float(r["seconds"]))
    impls = ["Fable", "Codex", "Claude new+цикл", "Claude realloc", "std::vector libstdc++", "std::vector libc++"]
    icol = ["#1f77b4", "#ff7f0e", "#2ca02c", "#98df8a", "#9467bd", "#c5b0d5"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
    for ax, (mode, n, title) in zip(axes, [("x2", 1_000_000, "×2, 1 млн"), ("x2", 10_000_000, "×2, 10 млн"),
                                           ("add10", 200_000, "+10, 200 тыс.")]):
        xs, ms, lo, hi, cs = [], [], [], [], []
        for i, (name, col) in enumerate(zip(impls, icol)):
            if (name, mode, n) not in cm:
                continue
            v = [t * 1e3 for t in cm[(name, mode, n)]]
            xs.append(name.replace(" ", "\n", 1))
            ms.append(median(v)); lo.append(median(v) - min(v)); hi.append(max(v) - median(v)); cs.append(col)
        ax.bar(range(len(xs)), ms, yerr=[lo, hi], color=cs, capsize=3)
        ax.set_xticks(range(len(xs)), xs, fontsize=7)
        ax.set(ylabel="мс (медиана, мин–макс из 7)", title=title)
        if mode == "add10":
            ax.set_yscale("log")
        for i, m in enumerate(ms):
            ax.text(i, m, f"{m:.2f}" if m < 100 else f"{m:.0f}", ha="center", va="bottom", fontsize=7)
    fig.suptitle("10. Все реализации на одном стенде (отдельный процесс на замер, старт с пустого объекта)")
    save(fig, "10_implementations.png")
    summary["compare"] = {f"{a}|{b}|{c}": [median(v), min(v), max(v)] for (a, b, c), v in cm.items()}

# ---------------------------------------------------------------- 11 reuse (теория)
fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
kk = [1.2 + i * 0.01 for i in range(141)]
ratio = [1 / (k * (k - 1)) for k in kk]
axes[0].plot(kk, ratio)
axes[0].axhline(1, color="k", lw=0.8)
axes[0].axvline(PHI, color="goldenrod", lw=1)
axes[0].text(PHI + 0.02, 3, "φ ≈ 1.618", color="goldenrod")
axes[0].set(yscale="log", xlabel="множитель k", ylabel="(сумма освобождённых блоков) / (новый блок)",
            title="Предел при многих перевыделениях: 1/(k(k−1))")


def first_reuse(k, limit=60):
    # блоки 1, k, k^2, ...; пока копируем в блок m, блок m-1 ещё занят; освобождены 0..m-2, лежат подряд
    sizes = [1.0]
    for m in range(1, limit):
        sizes.append(sizes[-1] * k)
        if sum(sizes[:m - 1]) >= sizes[m]:
            return m
    return None


ks2 = [1.1, 1.2, 1.3, 1.4, 1.45, 1.5, 1.55, 1.6, 1.618, 1.65, 1.7, 2.0]
fr = [first_reuse(k) for k in ks2]
axes[1].bar(range(len(ks2)), [f if f else 0 for f in fr], color=["#2ca02c" if f else "#d62728" for f in fr])
axes[1].set_xticks(range(len(ks2)), [str(k) for k in ks2], fontsize=8)
for i, f in enumerate(fr):
    axes[1].text(i, (f or 0) + 0.2, str(f) if f else "∞", ha="center", fontsize=9, color="k" if f else "#d62728")
axes[1].set(xlabel="множитель k", ylabel="номер перевыделения",
            title="Номер перевыделения, с которого новый блок\nпомещается в освобождённое место (∞ — никогда)")
fig.suptitle("11. Почему MSVC и folly берут 1.5, а не 2: повторное использование памяти (модель)", y=1.04)
save(fig, "11_memory_reuse_model.png")
summary["first_reuse"] = dict(zip(map(str, ks2), fr))

# ---------------------------------------------------------------- 12 сравнение с отчётами Fable и Codex
fable = defaultdict(list)
for r in read("../../data/strategies.csv"):
    fable[(r["strategy"], int(r["n"]))].append(float(r["seconds"]))
codex = defaultdict(list)
for r in read("../../codex/data/times.csv"):
    codex[(r["strategy"], int(r["n"]))].append(float(r["seconds"]))
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
for ax, (lab, key_f, key_c, key_m) in zip(axes, [("+10", "+10", "add_10", "+10"), ("×2", "x2", "mul_2", "x2")]):
    for src, data, key, mk in [("Fable (new+цикл)", fable, key_f, "o"), ("Codex (realloc)", codex, key_c, "s"),
                               ("Claude (new+цикл)", st, key_m, "^")]:
        xs = sorted(n for (s, n) in data if s == key and n <= 10_000_000)
        ax.plot([x / 1e6 for x in xs], [median(data[(key, x)]) * 1e3 for x in xs], marker=mk, ms=4, label=src)
    ax.set(yscale="log", xlabel="n, млн", ylabel="мс", title=f"Стратегия {lab}")
    ax.legend(fontsize=8)
fig.suptitle("12. Одни и те же стратегии в трёх отчётах: расхождение +10 — это realloc, а не «быстрый +10»")
save(fig, "12_reports_side_by_side.png")

with open(D / "summary.json", "w") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
print("plots ok")
