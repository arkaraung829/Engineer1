# tools.py
# These are the functions Claude can call to interact with network devices.
# Claude never runs commands directly — it asks us to run them, and we return the results.

import os
import sys
from datetime import datetime
import paramiko

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────


def _log(msg: str):
    """Progress output. Goes to stderr — stdout must stay clean because
    MCP stdio clients (Claude Desktop) speak JSON-RPC over stdout."""
    print(msg, file=sys.stderr)

# Optional jump host — only needed when running the agent from OUTSIDE the
# lab (e.g. your Mac): set JUMP_HOST to the GCP VM's current external IP.
# When the agent runs on the EVE-NG VM itself, leave JUMP_HOST unset and
# devices are reached directly. (GCP external IPs change on VM restart —
# never hardcode one here.)
JUMP_HOST = os.environ.get("JUMP_HOST", "")
JUMP_USER = os.environ.get("JUMP_USER", "ayethandaraung")
JUMP_KEY  = os.path.expanduser("~/.ssh/google_compute_engine")

# Default credentials for EVE-NG lab devices
DEFAULT_USERNAME = "cisco"
DEFAULT_PASSWORD = "cisco123"
DEFAULT_ENABLE   = "cisco"


def _open_jump_channel(device_host: str, device_port: int = 22):
    """
    Open an SSH channel through the GCP VM jump host to reach
    a device inside EVE-NG that is not directly reachable from your Mac.

    Flow: Your Mac → GCP VM (jump host) → Router inside EVE-NG
    """
    jump = paramiko.SSHClient()
    jump.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    jump.connect(
        JUMP_HOST,
        username=JUMP_USER,
        key_filename=JUMP_KEY,
        timeout=10
    )

    # Open a direct TCP channel from jump host to the device
    transport = jump.get_transport()
    channel = transport.open_channel(
        "direct-tcpip",
        (device_host, device_port),
        ("127.0.0.1", 0)
    )
    return channel


def ssh_exec(host: str, command: str) -> str:
    """
    Run a Cisco IOS show command on a device via SSH.

    Parameters:
        host    — the device IP address inside EVE-NG (e.g. "192.168.0.10")
        command — the IOS command to run (e.g. "show ip bgp summary")

    Returns:
        The raw text output from the device
    """

    # Real device — direct SSH, or through the jump host if one is set
    try:
        from netmiko import ConnectHandler

        device = {
            "device_type": "cisco_ios",
            "host": host,
            "username": DEFAULT_USERNAME,
            "password": DEFAULT_PASSWORD,
            "secret":   DEFAULT_ENABLE,
            "timeout":  20,
        }

        if JUMP_HOST:
            _log(f"\n  [SSH] {JUMP_HOST} → {host}> {command}")
            device["sock"] = _open_jump_channel(host)
        else:
            _log(f"\n  [SSH] {host}> {command}")

        with ConnectHandler(**device) as connection:
            connection.enable()           # enter enable mode
            output = connection.send_command(command)

        return output

    except Exception as error:
        via = f" via {JUMP_HOST}" if JUMP_HOST else ""
        return f"ERROR connecting to {host}{via}: {str(error)}"


def save_report(content: str, filename: str = "") -> str:
    """
    Save a diagnosis report to a file in the reports/ folder.

    Parameters:
        content  — the report text to save
        filename — optional filename (auto-generated if not provided)

    Returns:
        The path where the file was saved
    """
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"report_{timestamp}.md"

    if not filename.endswith(".md"):
        filename += ".md"

    filepath = os.path.join(reports_dir, filename)

    with open(filepath, "w") as file:
        file.write(content)

    _log(f"\n  [REPORT] Saved to: {filepath}")
    return f"Report saved to: {filepath}"
