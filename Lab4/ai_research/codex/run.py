"""Build, test, measure and plot. Optional --journal takes the original Sem8.zip."""
import argparse
import csv
import os
from pathlib import Path
import random
import subprocess
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
DATA = HERE / "data"


def compile_program(name, *args):
    executable = BUILD / (name + (".exe" if os.name == "nt" else ""))
    subprocess.run(["g++", "-std=c++20", "-O2", "-Wall", "-Wextra", "-Wpedantic",
                    *args, "-o", executable], cwd=HERE, check=True)
    return executable


def compare(archive):
    source = BUILD / "journal"
    source.mkdir(exist_ok=True)
    with ZipFile(archive) as zipped:
        for name in ("container.h", "container.cpp"):
            (source / name).write_bytes(zipped.read(name))
    programs = {
        "Codex": compile_program("compare-codex", "compare.cpp"),
        "Fable": compile_program("compare-fable", "-DUSE_FABLE", "compare.cpp", "../../subvector.cpp"),
        "Journal": compile_program("compare-journal", "-DUSE_JOURNAL", "-I", source,
                                   "compare.cpp", source / "container.cpp"),
    }
    rng = random.Random(37)
    with (DATA / "comparison.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["implementation", "mode", "n", "repeat", "seconds", "checksum"])
        for repeat in range(1, 6):
            jobs = [(name, "double", n) for name in programs for n in (1000000, 10000000)]
            jobs += [(name, "add10", 200000) for name in ("Codex", "Fable")]
            rng.shuffle(jobs)
            for name, mode, n in jobs:
                run = subprocess.run([programs[name], mode, str(n)], check=True,
                                     capture_output=True, text=True)
                # Journal prints an additional line from its destructor.
                seconds, checksum = run.stdout.splitlines()[0].split(",")
                writer.writerow([name, mode, n, repeat, seconds, checksum])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--measure-only", action="store_true", help="write CSVs without plotting")
    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    subprocess.run([compile_program("tests", "tests.cpp")], check=True)
    subprocess.run([compile_program("benchmark", "benchmark.cpp"), DATA], check=True)
    if args.journal:
        compare(args.journal)
    plot = [sys.executable, HERE / "plot.py"]
    if args.journal:
        plot.append("--comparison")
    if not args.measure_only:
        subprocess.run(plot, check=True)
