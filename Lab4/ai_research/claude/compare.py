"""Общий стенд: Fable, Codex, DeepSeek, Claude (new+цикл и realloc), std::vector (libstdc++ и libc++).
Каждое измерение — отдельный процесс, порядок перемешан, 7 раундов. Пишет data/compare.csv."""
import csv
import random
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
B = HERE / "build"
F = ["-std=c++20", "-O2", "-Wall", "-Wextra"]

builds = {
    "Fable": ["g++", *F, "-DIMPL_FABLE", "compare.cpp", "../../subvector.cpp"],
    "Codex": ["g++", *F, "-DIMPL_CODEX", "compare.cpp"],
    "DeepSeek": ["g++", *F, "-DIMPL_DEEPSEEK", "compare.cpp"],
    "Claude new+цикл": ["g++", *F, "compare.cpp",],
    "Claude realloc": ["g++", *F, "-DIMPL_CLAUDE_REALLOC", "compare.cpp",],
    "std::vector libstdc++": ["g++", *F, "-DIMPL_STD", "compare.cpp"],
    "std::vector libc++": ["clang++", "-stdlib=libc++", *F, "-DIMPL_STD", "compare.cpp"],
}
B.mkdir(exist_ok=True)
exe = {}
for i, (name, cmd) in enumerate(builds.items()):
    out = B / f"compare_{i}"
    subprocess.run([*cmd, "-o", str(out)], cwd=HERE, check=True)
    exe[name] = out

jobs = []
for name in exe:
    jobs += [(name, "x2", 1_000_000), (name, "x2", 10_000_000)]
    if not name.startswith("std"):
        jobs.append((name, "add10", 200_000))

rng = random.Random(11)
with open(HERE / "data" / "compare.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["implementation", "mode", "n", "round", "seconds"])
    for r in range(1, 8):
        rng.shuffle(jobs)
        for name, mode, n in jobs:
            out = subprocess.run([str(exe[name]), mode, str(n)], check=True, capture_output=True, text=True)
            w.writerow([name, mode, n, r, out.stdout.split(",")[0]])
        print("round", r)
