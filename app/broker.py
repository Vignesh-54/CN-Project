#!/usr/bin/env python3
"""Broker: one listener thread per topic port, one handler thread per connection.
First line sent by a client is 'SUB' or 'PUB'. Publishers' lines are forwarded to that topic's subscribers.
Unsubscribing = the subscriber closes its connection to that topic's port."""
import os, socket, sys, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import TOPIC_PORTS

subs = {t: {} for t in TOPIC_PORTS}          # topic -> {conn: send_lock}
counts = {t: 0 for t in TOPIC_PORTS}
lock = threading.Lock()


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def handle(conn, addr, topic):
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    f = conn.makefile("r")
    role = "?"
    try:
        role = f.readline().strip()
        if role == "SUB":
            with lock:
                subs[topic][conn] = threading.Lock()
            log(f"SUB  {topic} <- {addr[0]}:{addr[1]}")
            for _ in f:          # blocks until the subscriber disconnects
                pass
        elif role == "PUB":
            log(f"PUB  {topic} <- {addr[0]}:{addr[1]}")
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = (line + "\n").encode()
                with lock:
                    targets = list(subs[topic].items())
                    counts[topic] += 1
                for s, slock in targets:
                    try:
                        with slock:            # keep messages from interleaving
                            s.sendall(data)
                    except OSError:
                        with lock:
                            subs[topic].pop(s, None)
        else:
            log(f"bad role '{role}' from {addr}")
    except OSError:
        pass
    finally:
        with lock:
            subs[topic].pop(conn, None)
        try:
            conn.close()
        except OSError:
            pass
        log(f"DISC {topic} {addr[0]}:{addr[1]} ({role})")


def listen(topic, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", port))
    s.listen(256)
    log(f"listening topic={topic} port={port}")
    while True:
        c, addr = s.accept()
        threading.Thread(target=handle, args=(c, addr, topic), daemon=True).start()


def stats():
    while True:
        time.sleep(5)
        with lock:
            log("STATS", {t: (len(subs[t]), counts[t]) for t in TOPIC_PORTS}, "(subs, msgs)")


if __name__ == "__main__":
    for t, p in TOPIC_PORTS.items():
        threading.Thread(target=listen, args=(t, p), daemon=True).start()
    threading.Thread(target=stats, daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
