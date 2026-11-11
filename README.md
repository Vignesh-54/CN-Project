# Pub-Sub over TCP + SDN (Mininet + Ryu)

```
config.py          shared contract (ports, IPs)         <- both, never edit alone
app/    (Person A) broker.py publisher.py subscriber.py loadgen.py analyze.py
sdn/    (Person B) topo.py controller.py reroute.py standin_server.py standin_client.py
results/           CSVs, graphs, flowstats.csv, events.log
```
Latency expectation: publisher->broker crosses the diamond; broker->subscriber stays on s4.
So end-to-end latency is about 10 ms on the upper path and about 40 ms on the lower path.

## Setup (both laptops, Ubuntu 20.04 VM)
```
sudo apt update && sudo apt install -y mininet openvswitch-switch xterm git python3-pip python3-venv python3-matplotlib
sudo service openvswitch-switch start
python3 -m venv ~/ryu-env && source ~/ryu-env/bin/activate
pip install "setuptools<58" "eventlet==0.30.2" ryu      # Person B + integration VM
```

## Person A (app layer)
1. Localhost test, 4 terminals (`export BROKER_IP=127.0.0.1`):
   `python3 app/broker.py` | `python3 app/subscriber.py --topics sports --log results/a.csv --interactive` |
   `python3 app/subscriber.py --topics news --log results/b.csv` | `python3 app/publisher.py --topic sports --rate 10 --duration 20`
   Type `sub news` / `unsub sports` in the interactive subscriber.
2. Mininet test without SDN: `sudo mn -c && sudo python3 app/loadgen.py --pubs 3 --subs 3 --duration 15 --simple`
3. Scalability sweep on the plain network (still useful for a baseline):
   `for n in 1 5 10 25 50; do sudo mn -c; sudo python3 app/loadgen.py --pubs $n --subs $n --duration 30 --simple --tag _plain; done`
4. `python3 app/analyze.py` and `python3 app/analyze.py --timeline results/run_5_5`

## Person B (SDN layer)
1. Terminal 1: `source ~/ryu-env/bin/activate && ryu-manager sdn/controller.py`
2. Terminal 2: `sudo mn -c && sudo python3 sdn/topo.py`
3. `mininet> pingall` (0% dropped), `mininet> h1 ping -c3 h3` (RTT about 20 ms)
4. Classification with stand-ins:
   ```
   mininet> h3 python3 sdn/standin_server.py 5001 &
   mininet> h1 python3 sdn/standin_client.py 5001 20 &
   mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s2 | grep tcp     # n_packets rising
   ```
   Repeat for 5002 and 5003 (separate rules increase).
5. Reroute: `python3 sdn/reroute.py sports lower` and re-run `dump-flows s3`: the counters move to s3, rtt in the client goes up (~20 ms -> ~80 ms for the stand-in's request/response).
   Back: `python3 sdn/reroute.py sports upper`. State: `curl http://127.0.0.1:8080/paths`
6. Check `results/flowstats.csv` is filling.

## Integration (one VM, in this order, stop at first failure)
1. Ryu + `sudo python3 sdn/topo.py`, `pingall` OK
2. `mininet> h3 python3 app/broker.py > results/broker.log 2>&1 &`
3. `mininet> h4 python3 app/subscriber.py --topics sports --log results/h4.csv &`
   `mininet> h1 python3 app/publisher.py --topic sports --rate 10 --duration 20` -> latency about 10 ms
4. Add news/weather subscribers on h5, publisher on h2: no cross-delivery
5. `dump-flows` per topic, `flowstats.csv` filling
6. Automated reroute experiment (new VM session, controller running):
   `sudo mn -c; sudo python3 app/loadgen.py --pubs 3 --subs 3 --duration 40 --reroute-at 20 --reroute-topic sports --reroute-path lower`
   `python3 app/analyze.py --timeline results/run_3_3` -> sports jumps about 10 -> 40 ms, news stays flat
7. Sweep: `for n in 1 5 10 25 50; do sudo mn -c; sudo python3 app/loadgen.py --pubs $n --subs $n --duration 30; done; python3 app/analyze.py`
8. Live demo: `mininet> xterm h4` then `python3 app/subscriber.py --topics sports --log results/live.csv --interactive`, type `sub news`.

## Troubleshooting
- Always `sudo mn -c` first; `sudo pkill -f broker.py` for stale brokers.
- Start Ryu BEFORE Mininet. Ping fails -> check Ryu terminal printed "switch s1..s4 configured".
- `Address already in use` -> stale process. No output in files -> use `flush=True`.
