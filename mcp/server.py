# mcp/server.py
# The MCP server — exposes your tools to any Claude app (Claude Desktop, Claude Code, other agents).
# Other engineers run this file on a shared server and connect their Claude to it.
#
# Architecture:
#   Claude Desktop / agent.py
#           │
#           │  MCP protocol (JSON-RPC)
#           ▼
#       server.py       ← YOU ARE HERE
#           │
#           │  imports
#           ▼
#       tools.py        ← same functions agent.py uses
#           │
#           ▼
#       Cisco devices / simulator

import sys
import os

# Tell Python where to find tools.py (one folder up from mcp/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from tools import ssh_exec, save_report

# Create the MCP server — "network-ops" is the name other engineers see
mcp = FastMCP("network-ops")


# ─────────────────────────────────────────────
# TOOL 1: SSH into a Cisco device
# ─────────────────────────────────────────────
# @mcp.tool() registers this function as an MCP tool.
# Claude reads the docstring to understand when and how to use it.
@mcp.tool()
def run_ssh(host: str, command: str) -> str:
    """
    Run a Cisco IOS show command on a network device via SSH.
    Use this to check BGP status, interface status, routing table,
    system logs, CPU, memory, and any other network state.
    Always gather data with this tool before drawing conclusions.
    """
    return ssh_exec(host, command)


# ─────────────────────────────────────────────
# TOOL 2: Save a diagnosis report to a file
# ─────────────────────────────────────────────
@mcp.tool()
def write_report(content: str, filename: str = "") -> str:
    """
    Save a diagnosis report to a markdown file.
    Call this at the end of every investigation to save findings.
    Format the content with sections: Summary, Root Cause, Evidence, Fix Commands.
    """
    return save_report(content, filename)


# ─────────────────────────────────────────────
# START THE SERVER
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Startup messages must go to stderr: stdio MCP clients (Claude
    # Desktop) speak JSON-RPC over stdout, and any stray print there
    # corrupts the protocol handshake.
    print("network-ops MCP server starting (stdio)...", file=sys.stderr)
    print("Tools available: run_ssh, write_report", file=sys.stderr)
    mcp.run()
