#!/usr/bin/env python3
"""Stand-in for the broker so Person B can test classification/rerouting without Person A's code.
(based on tcpServer.py)   usage: python3 sdn/standin_server.py 5001"""
import socket, sys, threading

port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', port))
s.listen(5)
print("stand-in server listening on", port, flush=True)


def serve(c, addr):
    print('Got connection from', addr, flush=True)
    c.send('Thank you for connecting\n'.encode())
    while c.recv(1024):          # keep echoing so traffic keeps flowing
        c.send(b'ack\n')
    c.close()


while True:
    c, addr = s.accept()
    threading.Thread(target=serve, args=(c, addr), daemon=True).start()
