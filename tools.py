# tools.py
# These are the functions Claude can call to interact with network devices.
# Claude never runs commands directly — it asks us to run them, and we return the results.

import simulator
import os
from datetime import datetime
import paramiko

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Flip to True to use the fake Cisco device instead of real SSH
USE_SIMULATOR = False

# Jump host = your GCP VM (the bridge between your Mac and EVE-NG devices)
JUMP_HOST = "34.41.103.220"
JUMP_USER = "ayethandaraung"
JUMP_KEY  = "/Users/ayethandaraung/.ssh/google_compute_engine"

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
        The raw text output from the device (or simulator)
    """

    if USE_SIMULATOR:
        print(f"\n  [SSH] {host}> {command}")
        result = simulator.get_response(command)
        print(f"  [OUTPUT PREVIEW] {result.strip()[:120]}...")
        return result

    # Real device via jump host
    try:
        from netmiko import ConnectHandler

        print(f"\n  [SSH] {JUMP_HOST} → {host}> {command}")

        # Open channel through GCP VM to reach device inside EVE-NG
        channel = _open_jump_channel(host)

        device = {
            "device_type": "cisco_ios",
            "host": host,
            "username": DEFAULT_USERNAME,
            "password": DEFAULT_PASSWORD,
            "secret":   DEFAULT_ENABLE,
            "sock":     channel,          # use the jump channel instead of direct TCP
        }

        with ConnectHandler(**device) as connection:
            connection.enable()           # enter enable mode
            output = connection.send_command(command)

        return output

    except Exception as error:
        return f"ERROR connecting to {host} via {JUMP_HOST}: {str(error)}"


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

    print(f"\n  [REPORT] Saved to: {filepath}")
    return f"Report saved to: {filepath}"
