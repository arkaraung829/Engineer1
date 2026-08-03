# Engineer1 — AI Network Troubleshooting Agent

An AI agent that troubleshoots Cisco networks. You describe a problem in plain
English; the agent decides which `show` commands to run, SSHes into the devices,
reads the output, and gives you a root-cause diagnosis with fix commands.

It runs against a **real 4-device lab** (two routers, two switches) built on
EVE-NG (a network emulator) hosted on a Google Cloud VM.

---

## 1. The big picture (read this first)

There are **three layers**. Everything in this repo belongs to one of them:

```
┌─────────────────────────────────────────────────────────────┐
│  BRAIN     Claude (the LLM) decides what commands to run and  │
│            interprets the results.  →  agent.py, prompts/     │
├─────────────────────────────────────────────────────────────┤
│  HANDS     Code that actually connects to devices over SSH.   │
│            One function, ssh_exec().   →  tools.py             │
│            Exposed to other apps via   →  mcp/server.py        │
├─────────────────────────────────────────────────────────────┤
│  LAB       The network being troubleshot: 4 Cisco devices in  │
│            EVE-NG on a GCP VM.  →  topology/, startup.sh,      │
│            scripts/, lab/                                      │
└─────────────────────────────────────────────────────────────┘
```

The golden rule that makes it safe: **the LLM never touches a device directly.**
It *asks* our code to run a command; our code runs it and hands back the text.
That boundary is where all safety controls live (today: read-only `show`
commands only).

## 2. What happens when you ask a question

```
You: "why is my port-channel down?"
        │
        ▼
  agent.py  ──(1) sends your question + the rules to──▶  Claude
        ▲                                                   │
        │                                          (2) "run 'show etherchannel
        │                                               summary' on 192.168.0.12"
        │                                                   │
        ▼                                                   ▼
  tools.py.ssh_exec()  ──(3) SSH to the device, run it──▶  Cisco switch
        │                                                   │
        │  (4) returns the raw text output ◀────────────────┘
        ▼
  agent.py  ──(5) sends the output back to──▶  Claude
        │                                          │
        │              (6) loops steps 2-5 until Claude has enough evidence
        ▼                                          │
  Claude's final answer: "Po1 is suspended because member ports don't
  allow the same VLANs as the port-channel. Fix: ..."
```

This loop — **ask → tool call → run it → feed result back → repeat** — is the
core of every AI agent. In this project it's ~40 lines in `agent.py`.

## 3. File-by-file map

### The agent (BRAIN)
| File | What it does |
|---|---|
| `agent.py` | The main program. Runs the ask→tool→repeat loop, keeps conversation memory, defines which tools Claude may call. **Start reading here after tools.py.** |
| `prompts/network-agent.md` | Claude's instructions in plain English — its role, the device list, rules like "gather data before concluding." Edit this to change the agent's behavior. |

### Device access (HANDS)
| File | What it does |
|---|---|
| `tools.py` | The heart. `ssh_exec(host, command)` connects to a device and runs one command. Also `save_report()`. **The single place credentials and connection logic live — start here.** |
| `mcp/server.py` | Wraps `tools.py` as an **MCP server** so other apps (Claude Desktop, other engineers) can use the same tools. Also has lab start/stop tools. Thin — it just re-exposes `tools.py`. |

### The lab (INFRASTRUCTURE)
| File | What it does |
|---|---|
| `topology/topology.yml` | **Declares** the lab: which devices, how they connect. The source of truth for the network's shape. |
| `topology/configs/*.txt` | The Cisco config for each device (R1, R2, SW1, SW2). |
| `topology/build-topology.py` | **Builds** the lab in EVE-NG from `topology.yml` + the configs. Destructive: deletes and recreates the lab. Run by hand, never automatically. |
| `topology/validate.py` | Checks `topology.yml` produces a valid lab **without touching the VM**. Runs in CI and as a pre-flight before a rebuild. |
| `startup.sh` | Boots the lab on the VM: starts the devices, sets up networking, waits for SSH. Run after the VM powers on. |

### Automation / ops (DEVOPS)
| File | What it does |
|---|---|
| `scripts/lab-up.sh` | One command from your Mac: start the VM → sync code → boot the lab. |
| `scripts/lab-down.sh` | Gracefully stop the devices, then stop the VM (pauses billing). |
| `scripts/sync-reports.sh` | Pull agent-generated reports from the VM into this repo. |
| `.github/workflows/ci.yml` | CI: on every push, checks Python compiles, `tools.py` imports, topology is valid, shell scripts parse, and the MCP server responds. No VM needed. |
| `lab/install-eve-ng.sh`, `lab/setup-gcp-vm.sh` | One-time provisioning scripts — how the VM and EVE-NG were originally set up. Kept as documentation. |

### Docs & config
| File | What it does |
|---|---|
| `CLAUDE.md` | Project instructions (also read by the Claude Code CLI). |
| `AI-AGENT-ARCHITECTURE.md` | Conceptual study guide for agent architecture. |
| `INTERVIEW-NOTES.md` | Architecture talking points. |
| `setup-api-key.sh` | Local helper to set the Anthropic API key (gitignored). |
| `memory/conversation.json` | The agent's saved conversation history (gitignored, runtime state). |

## 4. Where things run: Mac vs GCP VM

**Same code, two places.** The repo on your **Mac** is where you edit and commit.
The **GCP VM** runs the code against the lab. Behaviour is controlled by
environment variables, not by different files:

| Env var | Effect |
|---|---|
| `JUMP_HOST=<vm-ip>` | Reach devices by tunnelling through the VM (set this when running from the Mac). Unset on the VM, where devices are directly reachable. |
| `MCP_TRANSPORT=http` | Run the MCP server as a shared HTTP service (used by the VM's systemd service). Default is `stdio` for a local Claude Desktop. |

Deployment to the VM happens via `scripts/lab-up.sh` (rsync), **not** on git push —
because the VM's IP changes on restart and it's often powered off.

## 5. The two DevOps patterns worth knowing

1. **Validate automatically, apply deliberately.** `topology.yml` + configs are
   *declarative desired state* (like Terraform files). CI validates them on every
   push, but the actual rebuild (`build-topology.py`) is a **human command** because
   it's destructive (deletes the lab, reboots devices). You don't auto-apply
   production network changes — the blast radius is too high.

2. **Deploy on bring-up, not on push.** The lab is an on-demand, ephemeral target
   (moving IP, often off). So code syncs when you start the lab, not on every
   commit. Match the delivery model to the target's lifecycle.

## 6. Common tasks

```bash
# Bring the whole lab up (from your Mac)
scripts/lab-up.sh                    # starts VM, syncs code, boots devices

# Run the agent (on the VM, after lab is up)
ssh <user>@<vm-ip>
cd /opt/network-mcp && venv/bin/python3 agent.py

# Rebuild the lab from scratch (on the VM) — destructive, ~4 min
cd /opt/network-mcp/topology && python3 build-topology.py topology.yml

# Check a topology change is valid before rebuilding (anywhere)
python3 topology/validate.py

# Pull reports back into the repo, then commit
scripts/sync-reports.sh <vm-ip>

# Shut the lab down (pauses VM billing)
scripts/lab-down.sh
```

## 7. Requirements

- Python 3.12+, `pip install anthropic netmiko fastmcp pyyaml paramiko`
- `export ANTHROPIC_API_KEY="..."`
- For the lab: a GCP VM running EVE-NG with the 4-device topology (see `lab/`).
