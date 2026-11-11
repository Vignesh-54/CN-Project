#!/usr/bin/env python3
"""Publisher: python3 app/publisher.py --topic sports --rate 10 --duration 60"""
import argparse, os, socket, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import BROKER_IP, TOPIC_PORTS


def connect(broker, port, tries=15):
    for _ in range(tries):
        try:
            s = socket.create_connection((broker, port), timeout=5)
            s.settimeout(None)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return s
        except OSError:
            time.sleep(1)
    sys.exit("publisher: cannot reach broker")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, choices=list(TOPIC_PORTS))
    ap.add_argument("--rate", type=float, default=10, help="messages per second")
    ap.add_argument("--count", type=int, default=0, help="0 = unlimited")
    ap.add_argument("--duration", type=float, default=0, help="seconds, 0 = unlimited")
    ap.add_argument("--broker", default=BROKER_IP)
    ap.add_argument("--id", default="0")
    ap.add_argument("--size", type=int, default=32, help="payload bytes")
    a = ap.parse_args()

    s = connect(a.broker, TOPIC_PORTS[a.topic])
    s.sendall(b"PUB\n")
    print(f"publisher {a.id} -> {a.topic} @ {a.rate}/s", flush=True)
    seq, interval = 0, 1.0 / a.rate
    nxt = time.time()
    end = time.time() + a.duration if a.duration else None
    payload = f"pub{a.id}-" + "x" * a.size
    try:
        while not (a.count and seq >= a.count) and not (end and time.time() >= end):
            s.sendall(f"{a.topic}|{seq}|{time.time():.6f}|{payload}\n".encode())
            seq += 1
            nxt += interval
            d = nxt - time.time()
            if d > 0:
                time.sleep(d)
    except (BrokenPipeError, ConnectionResetError):
        print("broker closed connection", flush=True)
    finally:
        s.close()
        print(f"publisher {a.id} done, sent {seq}", flush=True)


if __name__ == "__main__":
    main()
