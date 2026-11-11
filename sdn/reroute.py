#!/usr/bin/env python3
"""Move a topic to another path:  python3 sdn/reroute.py sports lower   |   python3 sdn/reroute.py sports upper
Logs 'time<TAB>REROUTE<TAB>topic<TAB>path' to results/events.log (used for the vertical line on graphs)."""
import os, sys, time, urllib.request
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
from config import REST_PORT


def reroute(topic, path, host="127.0.0.1", port=REST_PORT, logfile=None):
    req = urllib.request.Request(f"http://{host}:{port}/reroute/{topic}/{path}", method="POST")
    t = time.time()
    resp = urllib.request.urlopen(req, timeout=5).read().decode()
    logfile = logfile or os.path.join(ROOT, "results", "events.log")
    os.makedirs(os.path.dirname(logfile), exist_ok=True)
    with open(logfile, "a") as f:
        f.write(f"{t:.6f}\tREROUTE\t{topic}\t{path}\n")
    print("REROUTE", topic, path, f"{t:.3f}", resp)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: reroute.py <sports|news|weather> <upper|lower>")
    reroute(sys.argv[1], sys.argv[2])
