# build-topology.py
# Reads topology.yml and builds the lab in EVE-NG via REST API.
# Then SSHs into each device and pushes the base config.
#
# Usage:
#   python3 build-topology.py topology.yml
#
# Requirements:
#   pip install requests pyyaml netmiko

import sys
import time
import yaml
import requests
import urllib3
from netmiko import ConnectHandler

urllib3.disable_warnings()   # suppress SSL warnings for EVE-NG


# ─────────────────────────────────────────────
# EVE-NG API
# ─────────────────────────────────────────────

class EveNGAPI:
    def __init__(self, host, username, password):
        self.base = f"http://{host}/api"
        self.session = requests.Session()
        self.session.verify = False
        self._login(username, password)

    def _login(self, username, password):
        resp = self.session.post(f"{self.base}/auth/login",
                                 json={"username": username, "password": password, "html5": -1})
        resp.raise_for_status()
        print(f"  Logged into EVE-NG as {username}")

    def open_lab(self, name):
        resp = self.session.get(f"{self.base}/labs/{name}.unl")
        resp.raise_for_status()
        print(f"  Opened lab: {name}")

    def create_lab(self, name, description=""):
        payload = {
            "name":        name,
            "path":        "/",
            "description": description,
            "version":     "1",
            "author":      "admin",
            "body":        "",
        }
        resp = self.session.post(f"{self.base}/labs", json=payload)
        if resp.status_code == 409:
            print(f"  Lab '{name}' already exists, using it.")
            return name
        if not resp.ok:
            print(f"  EVE-NG error: {resp.status_code} {resp.text}")
            resp.raise_for_status()
        print(f"  Created lab: {name}")
        return name

    def get_templates(self):
        resp = self.session.get(f"{self.base}/list/templates/")
        resp.raise_for_status()
        return list(resp.json().get("data", {}).keys())

    def get_images(self, template):
        resp = self.session.get(f"{self.base}/list/images/{template}")
        resp.raise_for_status()
        return list(resp.json().get("data", {}).keys())

    def add_node(self, lab_name, node):
        payload = {
            "type":     "qemu",
            "template": node["type"],
            "image":    node["image"],
            "name":     node["name"],
            "cpu":      node.get("cpu", 1),
            "ram":      node.get("ram", 512),
            "ethernet": 4,
            "serial":   2,
            "console":  "telnet",
            "delay":    0,
            "left":     100,
            "top":      100,
            "icon":     "Router.png",
        }
        resp = self.session.post(f"{self.base}/labs/{lab_name}.unl/nodes", json=payload)
        if resp.status_code == 409:
            print(f"  Node '{node['name']}' already exists, skipping.")
            return None
        if not resp.ok:
            print(f"  EVE-NG error: {resp.status_code} {resp.text}")
            resp.raise_for_status()
        node_id = resp.json()["data"]["id"]
        print(f"  Added node: {node['name']} (id={node_id})")
        return node_id

    def get_nodes(self, lab_name):
        resp = self.session.get(f"{self.base}/labs/{lab_name}.unl/nodes")
        resp.raise_for_status()
        return resp.json().get("data", {})

    def add_network(self, lab_name, name, net_type="bridge"):
        payload = {"name": name, "type": net_type}
        resp = self.session.post(f"{self.base}/labs/{lab_name}.unl/networks", json=payload)
        resp.raise_for_status()
        net_id = resp.json()["data"]["id"]
        print(f"  Created network: {name} (id={net_id})")
        return net_id

    def connect_node_to_network(self, lab_name, node_id, interface_id, network_id):
        payload = {str(interface_id): network_id}
        resp = self.session.put(
            f"{self.base}/labs/{lab_name}.unl/nodes/{node_id}/interfaces",
            json=payload)
        resp.raise_for_status()

    def start_all(self, lab_name):
        resp = self.session.get(f"{self.base}/labs/{lab_name}.unl/nodes/start")
        resp.raise_for_status()
        print(f"  All nodes started.")


# ─────────────────────────────────────────────
# CONFIG PUSHER
# ─────────────────────────────────────────────

def push_config(node):
    """SSH into device and push base config line by line."""
    config_file = node.get("config")
    if not config_file:
        return

    print(f"\n  Pushing config to {node['name']} ({node['mgmt_ip']})...")

    with open(config_file, "r") as f:
        commands = [line.rstrip() for line in f
                    if line.strip() and not line.startswith("!")]

    device = {
        "device_type": "cisco_ios",
        "host":        node["mgmt_ip"],
        "username":    "cisco",
        "password":    "cisco123",
        "secret":      "cisco",
        "timeout":     30,
    }

    try:
        with ConnectHandler(**device) as conn:
            conn.enable()
            conn.send_config_set(commands)
            conn.save_config()
        print(f"  Config pushed to {node['name']} OK")
    except Exception as e:
        print(f"  ERROR pushing config to {node['name']}: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main(topology_file):
    print("\n================================================")
    print(" EVE-NG Topology Builder")
    print("================================================\n")

    with open(topology_file, "r") as f:
        topo = yaml.safe_load(f)

    eve   = topo["eve_ng"]
    lab   = topo["lab"]
    nodes = topo["nodes"]
    links = topo["links"]

    # Step 1 — connect to EVE-NG
    print("[1/4] Connecting to EVE-NG...")
    api = EveNGAPI(eve["host"], eve["username"], eve["password"])

    # Step 2 — create lab
    print(f"\n[2/4] Creating lab '{lab['name']}'...")
    api.create_lab(lab["name"], lab.get("description", ""))

    # Open lab so EVE-NG allows modifications
    api.open_lab(lab["name"])

    # Step 3 — add nodes
    print(f"\n[3/4] Adding nodes...")
    node_ids = {}
    for node in nodes:
        node_id = api.add_node(lab["name"], node)
        if node_id:
            node_ids[node["name"]] = node_id

    # Step 4 — create networks for each link and connect
    print(f"\n[4/4] Creating links...")
    for link in links:
        net_name = f"{link['from'].replace(':', '-')}__{link['to'].replace(':', '-')}"
        net_id = api.add_network(lab["name"], net_name)

        # Parse "R1:gi0/0" → name=R1, interface index
        from_name, from_iface = link["from"].split(":")
        to_name,   to_iface   = link["to"].split(":")

        from_id = node_ids.get(from_name)
        to_id   = node_ids.get(to_name)

        if from_id and to_id:
            from_idx = int(from_iface.replace("gi0/", ""))
            to_idx   = int(to_iface.replace("gi0/", ""))
            api.connect_node_to_network(lab["name"], from_id, from_idx, net_id)
            api.connect_node_to_network(lab["name"], to_id,   to_idx,   net_id)
            print(f"  Linked {link['from']} ↔ {link['to']}")

    # Start all nodes
    print("\n  Starting all nodes...")
    api.start_all(lab["name"])

    # Wait for devices to boot
    print("\n  Waiting 90 seconds for devices to boot...")
    time.sleep(90)

    # Push configs
    print("\n================================================")
    print(" Pushing base configs via SSH")
    print("================================================")
    for node in nodes:
        push_config(node)

    print("\n================================================")
    print(" Done! Topology is up.")
    print("================================================")
    print("\nDevices:")
    for node in nodes:
        print(f"  {node['name']:6}  {node['mgmt_ip']}")
    print("\nRun the AI agent to verify:")
    print("  /opt/network-mcp/venv/bin/python3 /opt/network-mcp/agent.py")


if __name__ == "__main__":
    topology_file = sys.argv[1] if len(sys.argv) > 1 else "topology.yml"
    main(topology_file)
