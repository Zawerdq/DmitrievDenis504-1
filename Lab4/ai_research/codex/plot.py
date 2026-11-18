"""Regenerate figures from CSVs. Pass --comparison to include the three implementations."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
DATA, PLOTS = ROOT / "data", ROOT / "plots"
MAIN = {"std": "std::vector", "add_10": "+10", "add_100": "+100",
        "mul_1.5": "×1,5", "mul_2": "×2"}


def read(name):
    with (DATA / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def series(ax, xs, groups, label=None, **kwargs):
    # All times in the CSV are seconds; the plots use milliseconds.
    ys = [median(group) * 1000 for group in groups]
    lower = [y - min(group) * 1000 for y, group in zip(ys, groups)]
    upper = [max(group) * 1000 - y for y, group in zip(ys, groups)]
    return ax.errorbar(xs, ys, yerr=[lower, upper], marker="o", markersize=4,
                       capsize=3, label=label, **kwargs)


def save(fig, name):
    fig.savefig(PLOTS / name, dpi=155, bbox_inches="tight")
    plt.close(fig)


def lab_figures():
    caps = read("std_capacity.csv")
    fig, ax = plt.subplots(figsize=(7.2, 4.1), layout="constrained")
    xs = [int(row["size"]) for row in caps]
    ax.step(xs, [int(row["capacity"]) for row in caps], where="post", label="capacity")
    ax.plot(xs, xs, "--", color="gray", label="size")
    ax.set(title="Ёмкость std::vector при последовательном добавлении",
           xlabel="Число элементов", ylabel="Число мест")
    ax.legend()
    save(fig, "01-std-capacity.png")

    rows = read("times.csv")
    times = defaultdict(list)
    for row in rows:
        times[row["strategy"], int(row["n"])].append(float(row["seconds"]))
    fig, ax = plt.subplots(figsize=(8.6, 4.8), layout="constrained")
    for name, label in MAIN.items():
        ns = sorted(n for key, n in times if key == name)
        series(ax, [n / 1e6 for n in ns], [times[name, n] for n in ns], label)
    ax.set(title="Время от начала заполнения · медиана и диапазон пяти прогонов",
           xlabel="Число элементов, млн", ylabel="Время, мс", yscale="log",
           xticks=range(1, 11))
    ax.legend(ncol=3)
    save(fig, "02-strategies.png")

    n = 1000000
    counts = {row["strategy"]: row for row in read("growth.csv")}
    for field, xlabel, filename in [("factor", "Множитель роста", "03-factor.png"),
                                    ("step", "Постоянная прибавка, мест", "04-step.png")]:
        params = sorted({(float(r[field]), r["strategy"]) for r in rows if float(r[field])})
        xs = [value for value, name in params]
        fig, (a, b) = plt.subplots(1, 2, figsize=(10.4, 4.2), layout="constrained")
        series(a, xs, [times[name, n] for value, name in params])
        a.set(ylabel="Время, мс", title="Медиана и диапазон пяти прогонов")
        if field == "factor":
            b.plot(xs, [(int(counts[name]["capacity"]) / n - 1) * 100 for _, name in params], "o-")
            b.set(title="Свободные места после заполнения", ylabel="Запас, % от числа элементов")
        else:
            b.plot(xs, [int(counts[name]["growths"]) for _, name in params], "o-")
            b.set(yscale="log", title="Запросы расширения", ylabel="Число запросов")
            a.set(yscale="log")
            for ax in (a, b):
                ax.set_xscale("log")
        for ax in (a, b):
            ax.set_xlabel(xlabel)
        fig.suptitle(f"{xlabel} · один миллион элементов")
        save(fig, filename)


def comparison_figure():
    times = defaultdict(list)
    for r in read("comparison.csv"):
        times[r["mode"], int(r["n"]), r["implementation"]].append(float(r["seconds"]))
    fig, axes = plt.subplots(1, 3, figsize=(10.9, 4), layout="constrained")
    for ax, (mode, n), title in zip(axes, [("double", 1000000), ("double", 10000000),
                                           ("add10", 200000)],
                                    ["×2 · 1 млн", "×2 · 10 млн", "+10 · 200 тыс."]):
        names = sorted(name for m, k, name in times if (m, k) == (mode, n))
        for x, name in enumerate(names):
            series(ax, [x], [times[mode, n, name]], color={"Codex": "#2166ac",
                   "Fable": "#b35806", "Journal": "#137455"}[name])
        ax.set(xticks=range(len(names)), xticklabels=names, title=title, ylabel="Время, мс")
        ax.set_xlim(-0.5, len(names) - 0.5)
        if mode == "add10":
            ax.set_yscale("log")
        else:
            ax.set_ylim(bottom=0)
    fig.suptitle("Один стенд · медиана и диапазон пяти заполнений")
    save(fig, "05-implementations.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", action="store_true")
    args = parser.parse_args()
    PLOTS.mkdir(exist_ok=True)
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.2})
    lab_figures()
    if args.comparison:
        comparison_figure()
