# build-topology.py
# Reads topology.yml and builds the lab in EVE-NG via REST API.
# Then SSHs into each device and pushes the base config.
#
# Usage:
#   /opt/network-mcp/venv/bin/python3 build-topology.py topology.yml
#
# Requirements:
#   pip install evengsdk pyyaml netmiko

import sys
import time
import yaml
from evengsdk.client import EvengClient
from netmiko import ConnectHandler


def push_config(node):
    """SSH into device and push base config."""
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


def main(topology_file):
    print("\n================================================")
    print(" EVE-NG Topology Builder")
    print("================================================\n")

    with open(topology_file, "r") as f:
        topo = yaml.safe_load(f)

    eve_cfg = topo["eve_ng"]
    lab     = topo["lab"]
    nodes   = topo["nodes"]
    links   = topo["links"]

    # Step 1 — connect to EVE-NG
    print("[1/4] Connecting to EVE-NG...")
    client = EvengClient(eve_cfg["host"], log_level="ERROR", ssl_verify=False)
    client.login(username=eve_cfg["username"], password=eve_cfg["password"])
    print(f"  Logged in at {eve_cfg['host']}")

    lab_path = f"/{lab['name']}.unl"

    # Step 2 — create lab
    print(f"\n[2/4] Creating lab '{lab['name']}'...")
    try:
        client.api.create_lab(
            name=lab["name"],
            path="/",
            description=lab.get("description", ""),
            author="admin",
            version="1",
            body=""
        )
        print(f"  Created lab: {lab['name']}")
    except Exception as e:
        if "already exists" in str(e) or "409" in str(e):
            print(f"  Lab already exists, continuing.")
        else:
            raise

    # Step 3 — add nodes
    print(f"\n[3/4] Adding nodes...")
    for i, node in enumerate(nodes):
        try:
            client.api.add_node(
                path=lab_path,
                template=node["type"],
                name=node["name"],
                image=node["image"],
                cpu=node.get("cpu", 1),
                ram=node.get("ram", 512),
                ethernet=4,
                serial=2,
                console="telnet",
                delay=0,
                left=100 + (i * 200),
                top=100,
            )
            print(f"  Added node: {node['name']}")
        except Exception as e:
            if "already exists" in str(e):
                print(f"  Node {node['name']} already exists, skipping.")
            else:
                print(f"  ERROR adding {node['name']}: {e}")

    # Step 4 — wire links between nodes
    print(f"\n[4/4] Creating links...")
    for link in links:
        try:
            from_name, from_iface = link["from"].split(":")
            to_name,   to_iface   = link["to"].split(":")

            client.api.connect_node_to_node(
                path=lab_path,
                src=from_name,
                src_label=from_iface,
                dst=to_name,
                dst_label=to_iface,
            )
            print(f"  Linked {link['from']} ↔ {link['to']}")
        except Exception as e:
            print(f"  ERROR linking {link.get('from')} ↔ {link.get('to')}: {e}")

    # Start all nodes
    print("\n  Starting all nodes...")
    try:
        client.api.start_all_nodes(path=lab_path)
        print("  All nodes started.")
    except Exception as e:
        print(f"  ERROR starting nodes: {e}")

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
    print("\nRun the AI agent:")
    print("  /opt/network-mcp/venv/bin/python3 /opt/network-mcp/agent.py")


if __name__ == "__main__":
    topology_file = sys.argv[1] if len(sys.argv) > 1 else "topology.yml"
    main(topology_file)
