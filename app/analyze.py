#!/usr/bin/env python3
"""Plots from results/.   python3 app/analyze.py                       -> scalability graphs
                         python3 app/analyze.py --timeline results/run_5_5   -> latency over time + reroute marker"""
import argparse, csv, glob, os, re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def load(run):
    rows = []
    for f in glob.glob(os.path.join(run, "sub_*.csv")):
        with open(f) as fh:
            for r in csv.DictReader(fh):
                rows.append((r["topic"], float(r["send_ts"]), float(r["recv_ts"]), float(r["latency_ms"])))
    return rows


def pct(v, p):
    v = sorted(v)
    return v[int(p * (len(v) - 1))] if v else 0


def scalability(outdir):
    pts = []
    for run in glob.glob(os.path.join(ROOT, "results", "run_*_*")):
        m = re.search(r"run_(\d+)_(\d+)$", run)
        rows = load(run)
        if not m or not rows:
            continue
        lat = [r[3] for r in rows]
        span = max(r[2] for r in rows) - min(r[2] for r in rows)
        pts.append((int(m.group(1)), int(m.group(2)), sum(lat) / len(lat), pct(lat, 0.95),
                    len(rows) / span if span else 0))
    pts.sort()
    if not pts:
        sys.exit("no results found in results/run_*_*")
    print("pubs subs  avg_ms  p95_ms  msgs/s")
    for p in pts:
        print(f"{p[0]:4d} {p[1]:4d} {p[2]:7.2f} {p[3]:7.2f} {p[4]:8.1f}")
    x = [p[0] for p in pts]
    plt.figure(); plt.plot(x, [p[2] for p in pts], "o-", label="average")
    plt.plot(x, [p[3] for p in pts], "s--", label="p95")
    plt.xlabel("number of publishers (= subscribers)"); plt.ylabel("latency (ms)")
    plt.title("Latency vs number of clients"); plt.legend(); plt.grid(True)
    plt.savefig(os.path.join(outdir, "latency_vs_clients.png"), dpi=150)
    plt.figure(); plt.plot(x, [p[4] for p in pts], "o-")
    plt.xlabel("number of publishers (= subscribers)"); plt.ylabel("delivered messages / sec")
    plt.title("Throughput vs number of clients"); plt.grid(True)
    plt.savefig(os.path.join(outdir, "throughput_vs_clients.png"), dpi=150)
    print("saved graphs in", outdir)


def timeline(run, outdir):
    rows = load(run)
    if not rows:
        sys.exit("no data in " + run)
    t0 = min(r[1] for r in rows)
    plt.figure(figsize=(9, 4.5))
    for topic in sorted({r[0] for r in rows}):
        bins = {}
        for t, s, _, l in rows:
            if t == topic:
                bins.setdefault(int(s - t0), []).append(l)
        xs = sorted(bins)
        plt.plot(xs, [sum(bins[x]) / len(bins[x]) for x in xs], label=topic)
    ev = os.path.join(run, "events.log")
    if os.path.exists(ev):
        for line in open(ev):
            p = line.strip().split("\t")
            if len(p) >= 4 and p[1] == "REROUTE":
                plt.axvline(float(p[0]) - t0, color="red", ls="--")
                plt.text(float(p[0]) - t0, plt.ylim()[1] * 0.95, f" reroute {p[2]}->{p[3]}", color="red", va="top")
    plt.xlabel("time (s)"); plt.ylabel("mean latency (ms)"); plt.title("Latency over time per topic")
    plt.legend(); plt.grid(True)
    out = os.path.join(outdir, "latency_timeline.png")
    plt.savefig(out, dpi=150); print("saved", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", help="run folder, e.g. results/run_5_5")
    a = ap.parse_args()
    out = os.path.join(ROOT, "results")
    timeline(a.timeline, out) if a.timeline else scalability(out)
