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
    Report the REAL lab state: GCP VM status and external IP, whether
    each Cisco device (192.168.0.10-13) answers SSH, and the tail of the
    most recent lab_up/lab_down output. Works no matter how the lab was
    started (Claude Desktop, terminal, GCP console).
    """
    lines = []

    # VM state straight from GCP — not from any local log
    vm_status, vm_ip = "", ""
    try:
        r = subprocess.run(
            ["gcloud", "compute", "instances", "list",
             "--filter=name=eve-ng-lab",
             "--format=value(status,networkInterfaces[0].accessConfigs[0].natIP)"],
            capture_output=True, text=True, env=SCRIPT_ENV, timeout=30)
        parts = r.stdout.strip().split("\t") if r.stdout.strip() else []
        vm_status = parts[0] if parts else ""
        vm_ip = parts[1] if len(parts) > 1 else ""
    except Exception as e:
        lines.append(f"gcloud check failed: {e}")

    if vm_status:
        lines.append(f"VM eve-ng-lab: {vm_status}"
                     + (f" at {vm_ip}" if vm_ip else ""))
    else:
        lines.append("VM eve-ng-lab: not found or gcloud not authed")

    # If the VM is up, probe each device's SSH port through it
    if vm_status == "RUNNING" and vm_ip:
        probe = ('for d in 10 11 12 13; do '
                 '(echo > /dev/tcp/192.168.0.$d/22) 2>/dev/null '
                 '&& echo "192.168.0.$d up" || echo "192.168.0.$d DOWN"; done')
        try:
            r2 = subprocess.run(
                ["ssh", "-i", os.path.expanduser("~/.ssh/google_compute_engine"),
                 "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
                 "-o", "ConnectTimeout=5", f"ayethandaraung@{vm_ip}", probe],
                capture_output=True, text=True, timeout=40)
            lines.append("Devices:\n" + (r2.stdout.strip() or r2.stderr.strip()))
        except Exception as e:
            lines.append(f"device probe failed: {e}")
        lines.append(f"JUMP_HOST for this Mac: {vm_ip}")

    try:
        with open(LAB_LOG, "r") as f:
            lines.append("--- last lab_up/lab_down output ---\n" + f.read()[-1000:])
    except FileNotFoundError:
        pass

    return "\n\n".join(lines)


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
