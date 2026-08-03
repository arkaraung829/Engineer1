#!/usr/bin/env python3
# validate.py — check topology.yml builds a valid lab WITHOUT touching the VM.
# Run before a rebuild, and in CI. Loads the topology, generates the .unl XML
# in memory, and asserts it is well-formed with the expected structure.
#
#   python3 topology/validate.py [topology.yml]

import sys
import os
import importlib.util
from xml.dom import minidom

HERE = os.path.dirname(os.path.abspath(__file__))


def load_builder():
    """Import build-topology.py despite the hyphen in its filename."""
    spec = importlib.util.spec_from_file_location(
        "builder", os.path.join(HERE, "build-topology.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(topology_file):
    import yaml
    builder = load_builder()

    # build_unl_xml opens config files by paths relative to the topology
    # dir (that's where it's normally run from), so match that here.
    os.chdir(HERE)

    with open(topology_file) as f:
        topo = yaml.safe_load(f)

    lab, nodes, links = topo["lab"], topo["nodes"], topo["links"]

    # Config files referenced by nodes must exist (embedded at build time)
    for n in nodes:
        cfg = n.get("config")
        if cfg and not os.path.exists(os.path.join(HERE, cfg)):
            raise SystemExit(f"FAIL: {n['name']} config not found: {cfg}")

    xml = builder.build_unl_xml(lab, nodes, links)

    # Must parse as valid XML
    dom = minidom.parseString(xml)

    # Every node's referenced network_id must exist as a defined network
    net_ids = {n.getAttribute("id") for n in dom.getElementsByTagName("network")}
    for iface in dom.getElementsByTagName("interface"):
        nid = iface.getAttribute("network_id")
        if nid and nid not in net_ids:
            raise SystemExit(
                f"FAIL: interface references undefined network_id {nid}")

    n_nodes = len(dom.getElementsByTagName("node"))
    n_nets = len(dom.getElementsByTagName("network"))
    n_cfgs = len(dom.getElementsByTagName("config"))
    if n_nodes != len(nodes):
        raise SystemExit(f"FAIL: expected {len(nodes)} nodes, got {n_nodes}")

    print(f"OK: {n_nodes} nodes, {n_nets} networks, {n_cfgs} embedded configs; "
          f"all interface network_ids resolve.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "topology.yml"))
