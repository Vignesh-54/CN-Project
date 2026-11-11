#!/usr/bin/env python3
"""Scalability experiment. Builds the Mininet network, starts broker + N publishers + M subscribers
(several processes per host), optionally triggers a reroute, and stores CSVs in results/run_<N>_<M>/.

  sudo python3 app/loadgen.py --pubs 10 --subs 10 --rate 5 --duration 30            # full SDN topology
  sudo python3 app/loadgen.py --pubs 10 --subs 10 --simple                           # plain single switch (Person A dev)
  sudo python3 app/loadgen.py --pubs 5 --subs 5 --duration 40 --reroute-at 20 --reroute-topic sports --reroute-path lower
"""
import argparse, os, subprocess, sys, time
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ROOT = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "sdn"))
from config import BROKER_IP, TOPIC_PORTS
from mininet.log import setLogLevel


def make_net(simple):
    if simple:
        from mininet.net import Mininet
        from mininet.topo import SingleSwitchTopo
        net = Mininet(topo=SingleSwitchTopo(5))
        net.start()
        return net
    from topo import build_net          # Person B's topology (starts net + static ARP)
    return build_net()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pubs", type=int, default=1)
    ap.add_argument("--subs", type=int, default=1)
    ap.add_argument("--rate", type=float, default=5, help="msgs/sec per publisher")
    ap.add_argument("--duration", type=float, default=30)
    ap.add_argument("--simple", action="store_true")
    ap.add_argument("--reroute-at", type=float, default=0)
    ap.add_argument("--reroute-topic", default="sports")
    ap.add_argument("--reroute-path", default="lower")
    ap.add_argument("--tag", default="", help="suffix for the result folder")
    a = ap.parse_args()

    setLogLevel("warning")
    out = os.path.join(ROOT, "results", f"run_{a.pubs}_{a.subs}{a.tag}")
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(".csv") or f == "events.log":
            os.remove(os.path.join(out, f))

    net = make_net(a.simple)
    time.sleep(3)                                   # let flow rules settle
    topics = list(TOPIC_PORTS)
    procs = []

    def run(host, cmd, logname=None):
        o = open(os.path.join(out, logname), "w") if logname else subprocess.DEVNULL
        procs.append(net.get(host).popen(["python3"] + cmd, stdout=o, stderr=subprocess.STDOUT))

    try:
        run("h3", [f"{ROOT}/app/broker.py"], "broker.log")
        time.sleep(1.5)
        for i in range(a.subs):
            run(["h4", "h5"][i % 2],
                [f"{ROOT}/app/subscriber.py", "--topics", topics[i % len(topics)],
                 "--log", f"{out}/sub_{i}.csv", "--broker", BROKER_IP])
        time.sleep(2 + a.subs * 0.05)
        t0 = time.time()
        for i in range(a.pubs):
            run(["h1", "h2"][i % 2],
                [f"{ROOT}/app/publisher.py", "--topic", topics[i % len(topics)], "--rate", str(a.rate),
                 "--duration", str(a.duration), "--id", str(i), "--broker", BROKER_IP])
        if a.reroute_at:
            time.sleep(a.reroute_at)
            from reroute import reroute
            try:
                reroute(a.reroute_topic, a.reroute_path, logfile=os.path.join(out, "events.log"))
            except Exception as e:
                print("reroute failed:", e)
            time.sleep(max(0, a.duration - a.reroute_at))
        else:
            time.sleep(a.duration)
        time.sleep(3)                               # let in-flight messages arrive
    finally:
        for p in procs:
            p.terminate()
        time.sleep(1)
        net.stop()
    print("results in", out)


if __name__ == "__main__":
    main()
