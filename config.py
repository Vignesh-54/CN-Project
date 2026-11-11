"""Shared contract between Person A (app) and Person B (sdn). Do NOT edit without telling the other person."""
import os

# For localhost testing:  BROKER_IP=127.0.0.1 python3 app/broker.py
BROKER_IP = os.environ.get("BROKER_IP", "10.0.0.3")

# One TCP port per topic -> the SDN controller classifies traffic by this port.
TOPIC_PORTS = {"sports": 5001, "news": 5002, "weather": 5003}

HOSTS = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3",
         "h4": "10.0.0.4", "h5": "10.0.0.5"}
# Roles: h1,h2 = publishers | h3 = broker | h4,h5 = subscribers

# Message  : topic|seq|send_timestamp|payload\n
# CSV log  : topic,seq,send_ts,recv_ts,latency_ms
REST_PORT = 8080   # Ryu REST API used by reroute.py
