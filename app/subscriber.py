#!/usr/bin/env python3
"""Subscriber with dynamic subscriptions.
  python3 app/subscriber.py --topics sports,news --log results/h4.csv --interactive
Interactive commands:  sub <topic> | unsub <topic> | list | quit"""
import argparse, csv, os, socket, sys, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import BROKER_IP, TOPIC_PORTS


class Subscriber:
    def __init__(self, broker, logpath):
        self.broker, self.socks = broker, {}
        self.lock, self.wlock = threading.Lock(), threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(logpath)), exist_ok=True)
        self.f = open(logpath, "w", newline="", buffering=1)   # line-buffered
        self.w = csv.writer(self.f)
        self.w.writerow(["topic", "seq", "send_ts", "recv_ts", "latency_ms"])

    def subscribe(self, topic):
        if topic not in TOPIC_PORTS:
            print("unknown topic", topic, flush=True)
            return
        with self.lock:
            if topic in self.socks:
                return
            for _ in range(15):
                try:
                    s = socket.create_connection((self.broker, TOPIC_PORTS[topic]), timeout=5)
                    break
                except OSError:
                    time.sleep(1)
            else:
                print("cannot reach broker", flush=True)
                return
            s.settimeout(None)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.sendall(b"SUB\n")
            self.socks[topic] = s
        threading.Thread(target=self.reader, args=(topic, s), daemon=True).start()
        print("subscribed", topic, flush=True)

    def unsubscribe(self, topic):
        with self.lock:
            s = self.socks.pop(topic, None)
        if s:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()
            print("unsubscribed", topic, flush=True)

    def reader(self, topic, s):
        buf = b""
        while True:                      # TCP is a stream: buffer and split on '\n'
            try:
                data = s.recv(4096)
            except OSError:
                break
            if not data:
                break
            now = time.time()
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                self.record(line.decode(errors="replace"), now)

    def record(self, line, recv_ts):
        p = line.split("|", 3)
        if len(p) < 4:
            return
        try:
            send_ts = float(p[2])
        except ValueError:
            return
        with self.wlock:
            self.w.writerow([p[0], p[1], f"{send_ts:.6f}", f"{recv_ts:.6f}",
                             f"{(recv_ts - send_ts) * 1000:.3f}"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default="")
    ap.add_argument("--log", default="results/sub.csv")
    ap.add_argument("--broker", default=BROKER_IP)
    ap.add_argument("--duration", type=float, default=0, help="0 = run until killed")
    ap.add_argument("--interactive", action="store_true", help="read sub/unsub from stdin (use in xterm)")
    a = ap.parse_args()

    sub = Subscriber(a.broker, a.log)
    for t in filter(None, a.topics.split(",")):
        sub.subscribe(t.strip())

    try:
        if a.interactive:
            for line in sys.stdin:
                cmd = line.split()
                if not cmd:
                    continue
                if cmd[0] == "sub" and len(cmd) > 1:
                    sub.subscribe(cmd[1])
                elif cmd[0] == "unsub" and len(cmd) > 1:
                    sub.unsubscribe(cmd[1])
                elif cmd[0] == "list":
                    print(list(sub.socks), flush=True)
                elif cmd[0] == "quit":
                    break
        elif a.duration:
            time.sleep(a.duration)
        else:
            threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for t in list(sub.socks):
            sub.unsubscribe(t)
        sub.f.close()


if __name__ == "__main__":
    main()
