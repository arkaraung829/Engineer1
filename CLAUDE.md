# Engineer1 — Network AI Agent

## What This Project Does
An AI agent that troubleshoots Cisco IOS network devices.
The agent uses Claude to decide what show commands to run, runs them via SSH, and gives a plain English diagnosis.

## How to Run
```bash
pip install anthropic netmiko     # install once
python agent.py                   # run the agent
```

## Key Files
| File | What it does |
|---|---|
| `agent.py` | Main script — entry point, runs everything |
| `tools.py` | ssh_exec() function — runs commands on devices |
| `prompts/network-agent.md` | Claude's instructions (goals + rules) |
| `AI-AGENT-ARCHITECTURE.md` | Architecture study guide |

## Simulator vs Real Device
- Agent runs ON the GCP VM → connects to devices directly
- Running from the Mac → set `JUMP_HOST=<gcp-vm-ip>` to tunnel device SSH through the GCP VM

## Environment Variable Required
```bash
export ANTHROPIC_API_KEY="your-key-here"
```
