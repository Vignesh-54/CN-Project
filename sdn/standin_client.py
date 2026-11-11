#!/usr/bin/env python3
"""Stand-in publisher (based on tcpClient.py).  usage: python3 sdn/standin_client.py 5001 [seconds]"""
import os, socket, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import BROKER_IP

port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 30
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((BROKER_IP, port))
print("connected to", BROKER_IP, port, flush=True)
print(s.recv(1024).decode().strip(), flush=True)
end = time.time() + secs
while time.time() < end:
    t = time.time()
    s.send(b'ping\n')
    s.recv(1024)
    print(f"rtt {(time.time()-t)*1000:.1f} ms", flush=True)
    time.sleep(1)
s.close()
