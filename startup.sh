#!/bin/bash
# startup.sh
# Run this on the GCP VM AFTER starting your EVE-NG lab in the web UI.
# Usage: bash startup.sh

echo "================================================"
echo " Network Lab Startup"
echo "================================================"

# Step 0 — Fix ownership so any user can run agent.py
echo ""
echo "[0/3] Fixing file permissions..."
sudo chown -R $(whoami):$(whoami) /opt/network-mcp/
echo "  Permissions set for $(whoami)."

# Step 0b — Install any missing Python packages
echo ""
echo "[0b/3] Checking Python packages..."
/opt/network-mcp/venv/bin/pip install requests pyyaml netmiko fastmcp -q && echo "  Packages OK."

# Step 1 — Set bridge IP so router is reachable
echo ""
echo "[1/3] Setting bridge IP 192.168.0.1 on vnet0_1..."
sudo ip addr add 192.168.0.1/24 dev vnet0_1 2>/dev/null || echo "  Already set, skipping."
ip addr show vnet0_1 | grep inet
echo "  Bridge ready."

# Step 2 — Restart MCP server to make sure it's running
echo ""
echo "[2/3] Starting MCP server..."
sudo systemctl restart network-mcp
sleep 2
sudo systemctl is-active network-mcp && echo "  MCP server running on port 8000." || echo "  ERROR: MCP server failed to start."

# Step 3 — Test router is reachable
echo ""
echo "[3/3] Testing router connectivity..."
ping -c 2 -W 2 192.168.0.10 > /dev/null 2>&1 \
  && echo "  Router 192.168.0.10 is reachable." \
  || echo "  Router 192.168.0.10 not reachable — make sure EVE-NG lab is started and router is powered on."

echo ""
echo "================================================"
echo " Done. To run the AI agent:"
echo "   cd /opt/network-mcp"
echo "   /opt/network-mcp/venv/bin/python3 agent.py"
echo "================================================"
