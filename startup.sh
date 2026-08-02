#!/bin/bash
# startup.sh — one-command lab resume after a GCP VM restart.
# Starts the EVE-NG lab via the API, restores the management bridge IP,
# restarts the MCP server, and waits until every device answers SSH.
# Safe to re-run any time (all steps are idempotent).
#
# Usage: bash startup.sh

LAB="redundancy-lab"
EVE_API="http://127.0.0.1"        # loopback — works before the bridge has its IP
COOKIES="/tmp/eve-api.cookies"
MGMT_BRIDGE="vnet0_1"
MGMT_IP="192.168.0.1/24"
DEVICES="192.168.0.10 192.168.0.11 192.168.0.12 192.168.0.13"

echo "================================================"
echo " Network Lab Startup"
echo "================================================"

# Step 0 — Fix ownership so any user can run agent.py
echo ""
echo "[0/5] Fixing file permissions..."
sudo chown -R "$(whoami):$(whoami)" /opt/network-mcp/
echo "  Permissions set for $(whoami)."

# Step 1 — Start the EVE-NG lab via the API
echo ""
echo "[1/5] Starting EVE-NG lab '$LAB'..."
curl -s -c "$COOKIES" -X POST -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"eve","html5":-1}' \
     "$EVE_API/api/auth/login" > /dev/null
sudo rm -f "/opt/unetlab/labs/$LAB.unl.lock"
START_MSG=$(curl -s -b "$COOKIES" "$EVE_API/api/labs/$LAB.unl/nodes/start" \
            | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
echo "  ${START_MSG:-start request sent}"

# Step 2 — Wait for the management bridge, then give the host its IP
echo ""
echo "[2/5] Setting bridge IP ${MGMT_IP%/*} on $MGMT_BRIDGE..."
for i in $(seq 1 20); do
    if ip link show "$MGMT_BRIDGE" > /dev/null 2>&1; then
        sudo ip addr replace "$MGMT_IP" dev "$MGMT_BRIDGE"
        sudo ip link set "$MGMT_BRIDGE" up
        echo "  Bridge ready."
        break
    fi
    [ "$i" -eq 20 ] && echo "  ERROR: $MGMT_BRIDGE never appeared — did the lab start?"
    sleep 3
done

# Step 3 — Make sure Python packages are present
echo ""
echo "[3/5] Checking Python packages..."
/opt/network-mcp/venv/bin/pip install requests pyyaml netmiko fastmcp -q \
    && echo "  Packages OK."

# Step 4 — Restart MCP server
echo ""
echo "[4/5] Starting MCP server..."
sudo systemctl restart network-mcp
sleep 2
sudo systemctl is-active network-mcp > /dev/null \
    && echo "  MCP server running on port 8000." \
    || echo "  ERROR: MCP server failed to start."

# Step 5 — Wait for every device to answer SSH (boot takes ~2-3 min)
echo ""
echo "[5/5] Waiting for devices to boot and answer SSH..."
for ip in $DEVICES; do
    ok=""
    for i in $(seq 1 60); do
        if timeout 2 bash -c "</dev/tcp/$ip/22" 2>/dev/null; then
            echo "  $ip  SSH up"
            ok=1
            break
        fi
        sleep 5
    done
    [ -z "$ok" ] && echo "  $ip  NOT answering after 5 min — check its console in EVE-NG"
done

echo ""
echo "================================================"
echo " Done. To run the AI agent:"
echo "   cd /opt/network-mcp"
echo "   /opt/network-mcp/venv/bin/python3 agent.py"
echo "================================================"
