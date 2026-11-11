#!/usr/bin/env python3
"""Diamond topology with a remote (Ryu) controller.

            +-- s2 (5ms) --+                 upper path: s1-s2-s4  (5 ms + 5 ms)
 h1,h2 -- s1                s4 -- h3 broker, h4, h5 subscribers
            +-- s3 (20ms)-+                 lower path: s1-s3-s4  (20 ms + 20 ms)

Port map (the controller depends on it):
  s1: 1=h1 2=h2 3=s2 4=s3 | s2: 1=s1 2=s4 | s3: 1=s1 2=s4 | s4: 1=s2 2=s3 3=h3 4=h4 5=h5
Run:  sudo python3 sdn/topo.py      (start ryu-manager first)
"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import HOSTS
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel


def build_net(ctrl_ip="127.0.0.1", ctrl_port=6653):
    net = Mininet(controller=None, link=TCLink, switch=OVSSwitch, autoSetMacs=False)
    net.addController("c0", controller=RemoteController, ip=ctrl_ip, port=ctrl_port)

    s = {i: net.addSwitch(f"s{i}", dpid=f"{i:016x}", protocols="OpenFlow13") for i in range(1, 5)}
    h = {}
    for n, ip in HOSTS.items():
        i = int(n[1:])
        h[i] = net.addHost(n, ip=f"{ip}/24", mac=f"00:00:00:00:00:{i:02x}")

    # host links (switch ports fixed)
    net.addLink(h[1], s[1], port2=1)
    net.addLink(h[2], s[1], port2=2)
    net.addLink(h[3], s[4], port2=3)
    net.addLink(h[4], s[4], port2=4)
    net.addLink(h[5], s[4], port2=5)
    # upper path (fast)
    net.addLink(s[1], s[2], port1=3, port2=1, delay="5ms")
    net.addLink(s[2], s[4], port1=2, port2=1, delay="5ms")
    # lower path (slow)
    net.addLink(s[1], s[3], port1=4, port2=1, delay="20ms")
    net.addLink(s[3], s[4], port1=2, port2=2, delay="20ms")

    net.start()
    try:
        net.waitConnected()
    except Exception:
        time.sleep(3)
    net.staticArp()     # the diamond is a loop: no ARP flooding allowed
    return net


if __name__ == "__main__":
    setLogLevel("info")
    n = build_net()
    CLI(n)
    n.stop()
