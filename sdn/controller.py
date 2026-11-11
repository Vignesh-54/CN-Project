"""Ryu OpenFlow 1.3 controller: proactive per-topic flow rules, flow statistics, REST rerouting.
Run:  ryu-manager sdn/controller.py          (REST API on :8080)

 - priority 10 : default IP forwarding over the UPPER path (so ping/other traffic works)
 - priority 100: topic rules. match tcp_dst==port OR tcp_src==port (+ ipv4_dst) -> output per topic's current path
 - POST /reroute/<topic>/<upper|lower> moves one topic to the other path
 - every 2 s: flow stats -> results/flowstats.csv  (time,dpid,topic,packets,bytes)
"""
import csv, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import TOPIC_PORTS, HOSTS

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
STATS_CSV = os.path.join(ROOT, "results", "flowstats.csv")
TOPIC_PRIO, DEFAULT_PRIO = 100, 10


def tbl(d):  # {dpid: {"h1": port}} -> {dpid: {ip: port}}
    return {dpid: {HOSTS[h]: p for h, p in m.items()} for dpid, m in d.items()}


# dpid -> dst_ip -> output port      (see port map in topo.py)
UPPER = tbl({1: {"h1": 1, "h2": 2, "h3": 3, "h4": 3, "h5": 3},
             2: {"h1": 1, "h2": 1, "h3": 2, "h4": 2, "h5": 2},
             4: {"h1": 1, "h2": 1, "h3": 3, "h4": 4, "h5": 5}})
LOWER = tbl({1: {"h1": 1, "h2": 2, "h3": 4, "h4": 4, "h5": 4},
             3: {"h1": 1, "h2": 1, "h3": 2, "h4": 2, "h5": 2},
             4: {"h1": 2, "h2": 2, "h3": 3, "h4": 4, "h5": 5}})
PATHS = {"upper": UPPER, "lower": LOWER}


class PubSubSDN(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {"wsgi": WSGIApplication}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dps = {}
        self.current = {t: "upper" for t in TOPIC_PORTS}
        self.port2topic = {p: t for t, p in TOPIC_PORTS.items()}
        kwargs["wsgi"].register(RerouteAPI, {"app": self})
        os.makedirs(os.path.dirname(STATS_CSV), exist_ok=True)
        if not os.path.exists(STATS_CSV):
            with open(STATS_CSV, "w", newline="") as f:
                csv.writer(f).writerow(["time", "dpid", "topic", "packets", "bytes"])
        hub.spawn(self._poll)

    # ---------- flow helpers ----------
    def _add(self, dp, prio, match, out_port):
        p, o = dp.ofproto_parser, dp.ofproto
        inst = [p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, [p.OFPActionOutput(out_port)])]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=prio, match=match, instructions=inst))

    def _install_topic(self, dp, topic, path):
        table = PATHS[path].get(dp.id)
        port, p, o = TOPIC_PORTS[topic], dp.ofproto_parser, dp.ofproto
        if table is None:       # this switch is not on the chosen path -> remove stale rules
            for field in ("tcp_dst", "tcp_src"):
                m = p.OFPMatch(eth_type=0x0800, ip_proto=6, **{field: port})
                dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE, out_port=o.OFPP_ANY,
                                         out_group=o.OFPG_ANY, match=m))
            return
        for ip, out in table.items():
            for field in ("tcp_dst", "tcp_src"):     # client->broker and broker->client direction
                m = p.OFPMatch(eth_type=0x0800, ip_proto=6, ipv4_dst=ip, **{field: port})
                self._add(dp, TOPIC_PRIO, m, out)

    # ---------- switch connects ----------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        self.dps[dp.id] = dp
        p = dp.ofproto_parser
        for ip, out in UPPER.get(dp.id, {}).items():      # default forwarding
            self._add(dp, DEFAULT_PRIO, p.OFPMatch(eth_type=0x0800, ipv4_dst=ip), out)
        for topic, path in self.current.items():
            if dp.id in PATHS[path]:
                self._install_topic(dp, topic, path)
        self.logger.info("switch s%s configured", dp.id)

    # ---------- reroute ----------
    def set_path(self, topic, path):
        self.current[topic] = path
        for dp in self.dps.values():          # add new-path rules first, then remove old ones
            if dp.id in PATHS[path]:
                self._install_topic(dp, topic, path)
        for dp in self.dps.values():
            if dp.id not in PATHS[path]:
                self._install_topic(dp, topic, path)
        self.logger.info("REROUTE %s -> %s", topic, path)

    # ---------- statistics ----------
    def _poll(self):
        while True:
            hub.sleep(2)
            for dp in list(self.dps.values()):
                dp.send_msg(dp.ofproto_parser.OFPFlowStatsRequest(dp))

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def stats_reply(self, ev):
        agg = {t: [0, 0] for t in TOPIC_PORTS}
        for st in ev.msg.body:
            if st.priority != TOPIC_PRIO:
                continue
            port = st.match.get("tcp_dst") or st.match.get("tcp_src")
            t = self.port2topic.get(port)
            if t:
                agg[t][0] += st.packet_count
                agg[t][1] += st.byte_count
        now = time.time()
        with open(STATS_CSV, "a", newline="") as f:
            w = csv.writer(f)
            for t, (pk, by) in agg.items():
                w.writerow([f"{now:.3f}", ev.msg.datapath.id, t, pk, by])


class RerouteAPI(ControllerBase):
    def __init__(self, req, link, data, **config):
        super().__init__(req, link, data, **config)
        self.app = data["app"]

    @route("reroute", "/reroute/{topic}/{path}", methods=["POST"])
    def reroute(self, req, **kw):
        topic, path = kw["topic"], kw["path"]
        if topic not in TOPIC_PORTS or path not in PATHS:
            return Response(status=400, body="bad topic or path\n")
        self.app.set_path(topic, path)
        return Response(content_type="application/json", body=json.dumps(self.app.current))

    @route("paths", "/paths", methods=["GET"])
    def paths(self, req, **kw):
        return Response(content_type="application/json", body=json.dumps(self.app.current))
