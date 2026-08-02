# build-topology.py
# Writes EVE-NG lab file directly to disk (bypasses API locking issues).
# Then SSHs into each device and pushes base configs.
#
# Usage:
#   /opt/network-mcp/venv/bin/python3 build-topology.py topology.yml
#
# Requirements:
#   pip install pyyaml netmiko

import sys
import os
import time
import uuid
import yaml
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from netmiko import ConnectHandler

EVE_LABS_DIR = "/opt/unetlab/labs"


def build_unl_xml(lab, nodes, links):
    """Build the EVE-NG .unl XML lab file content."""

    lab_elem = Element("lab")
    lab_elem.set("name",           lab["name"])
    lab_elem.set("id",             str(uuid.uuid4()))
    lab_elem.set("version",        "1")
    lab_elem.set("script_timeout", "600")
    lab_elem.set("countdown",      "0")
    lab_elem.set("lock",           "0")
    lab_elem.set("sat",            "-1")
    lab_elem.set("description",    lab.get("description", ""))
    lab_elem.set("author",         "admin")
    lab_elem.set("body",           "")

    topology = SubElement(lab_elem, "topology")
    nodes_elem = SubElement(topology, "nodes")
    networks_elem = SubElement(topology, "networks")

    # Management network — pnet0 bridges devices to the GCP VM (192.168.0.0/24)
    # This is what allows SSH from the GCP VM to each device's mgmt interface
    MGMT_NET_ID = 0
    mgmt_net = SubElement(networks_elem, "network")
    mgmt_net.set("id",         "0")
    mgmt_net.set("type",       "pnet0")
    mgmt_net.set("name",       "Management")
    mgmt_net.set("left",       "400")
    mgmt_net.set("top",        "50")
    mgmt_net.set("visibility", "1")

    # Node positions — routers top row, switches bottom row
    node_positions = {}
    routers  = [n for n in nodes if n["type"] == "vios"]
    switches = [n for n in nodes if n["type"] == "viosl2"]
    router_spacing  = 400
    switch_spacing  = 400
    router_start_x  = 200
    switch_start_x  = 200
    router_y        = 150
    switch_y        = 450

    for i, n in enumerate(routers):
        node_positions[n["name"]] = (router_start_x + i * router_spacing, router_y)
    for i, n in enumerate(switches):
        node_positions[n["name"]] = (switch_start_x + i * switch_spacing, switch_y)

    # Build network map from links
    # Each link becomes a bridge network connecting two interfaces
    net_id = 1
    net_map = {}   # (node_name, iface) -> network_id
    labels  = []   # (text, canvas_x, canvas_y) for each link label
    for link in links:
        from_key  = link["from"]
        to_key    = link["to"]
        from_name = from_key.split(":")[0]
        to_name   = to_key.split(":")[0]
        net_map[from_key] = net_id
        net_map[to_key]   = net_id

        # Position network at midpoint between the two connected nodes
        fx, fy = node_positions.get(from_name, (300, 300))
        tx, ty = node_positions.get(to_name,   (300, 300))
        mid_x = (fx + tx) // 2
        mid_y = (fy + ty) // 2

        desc = link.get("description", f"Net{net_id}")
        net_elem = SubElement(networks_elem, "network")
        net_elem.set("id",         str(net_id))
        net_elem.set("type",       "bridge")
        net_elem.set("name",       desc)
        net_elem.set("left",       str(mid_x))
        net_elem.set("top",        str(mid_y))
        net_elem.set("visibility", "0")

        if desc:
            labels.append((desc, mid_x, mid_y))
        net_id += 1

    # Add nodes with calculated positions
    for node in nodes:
        node_elem = SubElement(nodes_elem, "node")
        node_elem.set("id",       str(nodes.index(node) + 1))
        node_elem.set("name",     node["name"])
        node_elem.set("type",     "qemu")
        node_elem.set("template", node["type"])
        node_elem.set("image",    node["image"])
        node_elem.set("console",  "telnet")
        node_elem.set("cpu",      str(node.get("cpu", 1)))
        node_elem.set("cpulimit", "0")
        node_elem.set("ram",      str(node.get("ram", 512)))
        node_elem.set("ethernet", "4")
        node_elem.set("serial",   "2")
        node_elem.set("delay",    "0")
        node_elem.set("icon",     "Router.png")
        node_elem.set("config",   "0")
        px, py = node_positions.get(node["name"], (100, 150))
        node_elem.set("left",     str(px))
        node_elem.set("top",      str(py))

        # Add interfaces
        mgmt_iface = node.get("mgmt_iface", 3)   # default: gi0/3 = management
        for iface_idx in range(4):
            iface_key = f"{node['name']}:gi0/{iface_idx}"
            iface_elem = SubElement(node_elem, "interface")
            iface_elem.set("id",   str(iface_idx))
            iface_elem.set("name", f"Gi0/{iface_idx}")
            iface_elem.set("type", "ethernet")
            if iface_idx == mgmt_iface:
                # Connect management interface to pnet0 (GCP VM bridge)
                iface_elem.set("network_id", str(MGMT_NET_ID))
            elif iface_key in net_map:
                iface_elem.set("network_id", str(net_map[iface_key]))

    # Add text labels at the midpoint of each link on the canvas.
    # EVE-NG textobject format: type="text" with a <data> child element
    # containing HTML with inline CSS that encodes position and style.
    if labels:
        objects_elem  = SubElement(lab_elem, "objects")
        textobjs_elem = SubElement(objects_elem, "textobjects")
        for idx, (text, lx, ly) in enumerate(labels, 1):
            t = SubElement(textobjs_elem, "textobject")
            t.set("id",   str(idx))
            t.set("name", text[:30])
            t.set("type", "text")
            data_elem = SubElement(t, "data")
            data_elem.text = (
                f'<div style="top:{ly - 18}px;left:{lx}px;z-index:1000;">'
                f'<p style="color:#000000;font-weight:bold;'
                f'background-color:transparent;font-size:14px;">'
                f'{text}</p></div>'
            )

    # Pretty print XML
    raw = tostring(lab_elem, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")
    # Remove the extra XML declaration minidom adds
    lines = pretty.split("\n")
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + \
           "\n".join(lines[1:])


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

    lab   = topo["lab"]
    nodes = topo["nodes"]
    links = topo["links"]

    lab_file = os.path.join(EVE_LABS_DIR, f"{lab['name']}.unl")

    # Step 0 — close and delete existing lab via API to release any lock
    print("[0/3] Closing existing lab if open...")
    import requests, urllib3
    urllib3.disable_warnings()
    s = requests.Session()
    s.verify = False
    s.post("http://192.168.0.1/api/auth/login",
           json={"username": "admin", "password": "eve", "html5": -1})
    # Stop all nodes first (ignore errors)
    s.get(f"http://192.168.0.1/api/labs/{lab['name']}.unl/nodes/stop")
    # Close the lab
    s.delete(f"http://192.168.0.1/api/labs/{lab['name']}.unl/close")
    # Delete the lab
    resp = s.delete(f"http://192.168.0.1/api/labs/{lab['name']}.unl")
    # Remove stale lock file if exists
    os.system(f"sudo rm -f {EVE_LABS_DIR}/{lab['name']}.unl.lock")
    if resp.ok:
        print(f"  Deleted existing lab.")
    else:
        print(f"  No existing lab found, continuing.")

    # Step 1 — build and write .unl file
    print("\n[1/3] Building lab file...")
    xml_content = build_unl_xml(lab, nodes, links)

    print(f"[2/3] Writing to {lab_file}...")
    tmp_file = f"/tmp/redundancy-lab.unl"
    with open(tmp_file, "w") as f:
        f.write(xml_content)
    os.system(f"sudo cp {tmp_file} {lab_file}")
    os.system(f"sudo chown www-data:www-data {lab_file}")
    os.system(f"sudo chmod 644 {lab_file}")
    print(f"  Lab file written OK.")

    # Step 2 — remove stale lock and start nodes
    print("\n[3/3] Loading lab into EVE-NG...")
    os.system(f"sudo rm -f {EVE_LABS_DIR}/{lab['name']}.unl.lock")
    s.get(f"http://192.168.0.1/api/labs/{lab['name']}.unl")
    r = s.get(f"http://192.168.0.1/api/labs/{lab['name']}.unl/nodes/start")
    msg = r.json().get("message", "")
    if "started" in msg.lower():
        print(f"  All nodes started.")
    else:
        print(f"  Start result: {msg}")
    nodes_resp = s.get(f"http://192.168.0.1/api/labs/{lab['name']}.unl/nodes")
    node_count = len(nodes_resp.json().get("data", {}))
    print(f"  {node_count} nodes in lab.")

    # Wait for boot
    print("\n  Waiting 90 seconds for devices to boot...")
    time.sleep(90)

    # Push configs
    print("\n================================================")
    print(" Pushing base configs via SSH")
    print("================================================")
    for node in nodes:
        push_config(node)

    print("\n================================================")
    print(" Done!")
    print("================================================")
    for node in nodes:
        print(f"  {node['name']:6}  {node['mgmt_ip']}")


if __name__ == "__main__":
    topology_file = sys.argv[1] if len(sys.argv) > 1 else "topology.yml"
    main(topology_file)
