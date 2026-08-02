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
# TOOLS 3-5: Lab lifecycle — start/stop the GCP lab from Claude Desktop
# ─────────────────────────────────────────────
# These run the repo's scripts on the Mac in the background (bring-up
# takes ~5 min) and log to a file so lab_status() can report progress.
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB_LOG = "/tmp/network-lab-lifecycle.log"

# Claude Desktop launches this server with a minimal environment —
# make sure the scripts can find gcloud (/opt/homebrew/bin wrapper)
SCRIPT_ENV = {**os.environ,
              "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"}


def _run_script_in_background(script: str) -> None:
    log = open(LAB_LOG, "w")
    subprocess.Popen(
        ["bash", os.path.join(REPO_ROOT, "scripts", script)],
        stdout=log, stderr=subprocess.STDOUT, env=SCRIPT_ENV,
    )


@mcp.tool()
def lab_up() -> str:
    """
    Start the GCP VM and boot the whole EVE-NG lab (4 Cisco devices).
    Runs in the background and takes about 5 minutes.
    Call lab_status() to watch progress; the final output includes the
    VM's new external IP (needed as JUMP_HOST to reach devices from
    this Mac).
    """
    _run_script_in_background("lab-up.sh")
    return ("Lab bring-up started in the background (~5 min: VM start, "
            "code sync, device boot). Call lab_status() to check progress.")


@mcp.tool()
def lab_down() -> str:
    """
    Gracefully shut the lab down: stops the Cisco devices first (saves
    their state), then stops the GCP VM so compute billing pauses.
    Runs in the background; call lab_status() to confirm completion.
    """
    _run_script_in_background("lab-down.sh")
    return ("Lab shutdown started in the background (~1 min). "
            "Call lab_status() to confirm.")


@mcp.tool()
def lab_status() -> str:
    """
    Show the progress/output of the most recent lab_up or lab_down run.
    The lab is fully up when the output shows all four devices
    (192.168.0.10-13) answering SSH and prints the VM IP.
    """
    try:
        with open(LAB_LOG, "r") as f:
            output = f.read()
    except FileNotFoundError:
        return "No lab_up/lab_down has been run since this server started."
    return output[-3000:] or "(script started, no output yet — check again shortly)"


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
