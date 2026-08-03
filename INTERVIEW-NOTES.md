# Interview Notes — Architecture Talking Points

Rehearsal notes for the Network Engineer + AI interview. Companion to
`AI-AGENT-ARCHITECTURE.md` (concepts) — this file is *my* system and how
it scales.

---

## 1. What I built (30-second opener)

> "I built an AI agent that troubleshoots Cisco networks. You describe a
> problem in plain English; the agent decides which show commands to run,
> SSHes into the devices, gathers evidence, and gives a root-cause
> diagnosis with fix commands. Behind it is a real 4-device lab — dual
> routers running eBGP, dual switches with an LACP port-channel — on
> EVE-NG in GCP, fully rebuilt from code in one command."

```
 YOU (plain English)
  ▼
 agent.py ──── ORCHESTRATOR: the loop + memory + system prompt (goals/rules)
  ▼  ▲
 Claude API ── BRAIN: picks commands, analyzes output   (never touches devices)
  ▼  ▲
 tools.py ──── HANDS: ssh_exec via Netmiko, save_report (my code executes)
  ▼
 EVE-NG lab ── R1↔R2 eBGP · routers→switches OSPF · SW1══SW2 LACP/VLANs/STP
```

Guardrails story, verbatim: **"The model requests actions; my code
executes them."** Read-only show commands; humans apply fixes.

## 2. Where MCP fits — one tool layer, many doors

```
  agent.py (direct import)     Claude Desktop (stdio)     engineers (HTTP+SSH tunnel)
          └──────────────────────────┴──────────────────────────┘
                              mcp/server.py — thin adapter
                              tools.py — THE enforcement point
```

- `tools.py` is the single place for credentials, simulator switch,
  jump-host logic, timeouts. Add an allowlist or audit log once — every
  consumer inherits it.
- The MCP server is deliberately thin: protocol adapter, no logic.
  (Anti-example: community splunk-mcp welds all logic into the server
  file — can't reuse, can't test without the server, guardrails per-tool.)
- Multi-engineer: shared HTTP MCP server co-located with the lab, bound
  to 127.0.0.1; engineers reach it via SSH tunnel. "Access control is
  SSH/IAM, not open ports."
- stdio gotcha I hit: Claude Desktop speaks JSON-RPC over stdout — any
  stray print() corrupts the handshake. All logging must go to stderr.

## 3. Scaling to many systems (Splunk, XDR, DNAC, IPAM…)

**Rule: one MCP server per SYSTEM, one library per domain, thin servers.**

```
netops/
├── lib/                          ← importable by agents/CLI/cron directly
│   ├── devices.py   (today's tools.py)
│   ├── splunk.py    dnac.py    ipam.py
└── servers/                      ← thin @mcp.tool() adapters, one per system
    ├── device_mcp.py  splunk_mcp.py  dnac_mcp.py  ipam_mcp.py
```

Why per-system servers, not one mega-server:
- **Tool selection**: LLMs choose worse as the tool menu grows; attach
  only the servers the task needs.
- **Credential/blast-radius isolation**: Splunk creds live only in the
  Splunk server's environment.
- **Independent lifecycle & placement**: redeploy dnac-mcp alone; run
  each server where its system is reachable.
- Cross-system workflows (diagnose_user: IPAM→DNAC→device→Splunk) belong
  in the **agent's reasoning loop**, not in mega-tools. Keep tools
  single-system; let the brain compose them.

Consistency at scale: shared result envelope (status/data/error same
shape everywhere), `get_*`/`list_*` naming, IPAM as the single
inventory source of truth.

One-liner: *"Per-domain MCP servers, each a thin adapter over an
importable library — servers own credentials and placement, the agent
owns cross-system reasoning. Five 100-line servers beat one 5000-line one."*

## 4. SSH vs NETCONF vs gNMI — transports, not domains

They do NOT get their own MCP servers. They are southbound drivers
inside the device library, selected per device from inventory:

```
device-mcp (ONE server) — tools speak INTENT:
   get_routing(device) · get_interfaces(device) · apply_config(device, change) · run_cli()
        ▼
 lib/devices/api.py — picks transport from inventory capability
   ├── cli.py (Netmiko)     → IOS 15 / legacy      (reads: fallback + parser)
   ├── netconf.py (ncclient)→ IOS-XE 16.3+          (WRITES: candidate→validate→diff→commit)
   └── gnmi.py (pygnmi)     → IOS-XR, modern        (READS: structured + streaming Subscribe)
```

- YANG is the common modeling layer; NETCONF and gNMI are protocols
  carrying YANG data. Heuristic the industry converged on:
  **NETCONF for writes, gNMI for reads/telemetry, CLI for legacy.**
- NETCONF's killer feature for agents: candidate datastore = the human
  approval gate is "review the diff, commit or discard" — far stronger
  than pasting CLI.
- Keep `run_cli` as an escape hatch: the LLM's IOS knowledge is too
  valuable to wall off, and old gear exists forever.
- The LLM never chooses transports — that's capability lookup, not
  reasoning. (Same pattern as Nornir connection plugins.)

One-liner: *"Transports are an implementation detail of the device
library, not tools. The agent asks for routing state; inventory decides
if that's gNMI, NETCONF, or Netmiko plus a parser. That's how one agent
supports a 2005 switch and a 2025 router."*

## 5. Three MCP designs I studied (comparison)

| | splunk-mcp (community) | mine | gNMIBuddy |
|---|---|---|---|
| Logic lives in | server file tool functions | tools.py, server is thin | layered lib (api→collectors→client) |
| Reusable outside MCP | no | yes (agent imports it) | yes (CLI + MCP frontends) |
| Transport | hand-rolled SSE (deprecated) | stdio + streamable HTTP | stdio + HTTP |
| Security posture | 0.0.0.0, no auth, arbitrary SPL | 127.0.0.1 + SSH tunnel, read-only | inventory-scoped, curated tools |
| Tool design | some near-duplicates (health/health_check/ping) | generic ssh_exec (flexible, trusts model) | 10 curated typed tools (constrained, safe) |

Trade-off to articulate: generic tool = flexibility, model expertise does
the work, demo shines. Curated typed tools = guardrails, structured
output, production shape. Evolution path: my generic tool grows into
gNMIBuddy-shaped curated tools as trust requirements rise.

## 6. Where enterprises actually are (2026)

1. **RAG chatbots** on runbooks — widespread.
2. **Read-only diagnosis copilots** — the current mainstream push
   (Telefónica, AIS ~30% NOC efficiency; TM Forum Incident Co-Pilot).
   **← my demo is exactly this stage.** Rule: AI reads, human writes.
3. **Governed auto-remediation** — leading edge (Cisco AI-native platform
   GA Apr 2026, ~85% MTTR claims; Juniper Mist; Gartner: 60% of netops
   tasks delegated to agents by 2028 — a forecast, not today).

Blocker isn't the AI — it's trust: scoped creds, allowlists, audit logs,
approval gates. Telcos lead, enterprises follow.

## 7. War stories (proof I debugged this for real)

- **LACP down, protocol innocent**: proved with tcpdump the virtual wire
  forwarded both directions but zero LACPDUs were sent; device logs said
  `vlan mask is different` — Po1 allowed VLANs 10,20 but member ports
  didn't. One line fixed it. (Rehearsable demo: remove the line, ask the
  agent "why is my port-channel degraded?")
- **My agent found a bug I missed**: its deep-dive report caught VLANs
  10/20 absent — VTP server mode ignores vlan commands in injected
  startup-configs; fixed with `vtp mode transparent`. The AI's written
  RCA was accurate down to the split-brain spanning tree.
- **EVE-NG reboot bug**: after VM restart, node bind-mounts vanish but
  `.prepared` markers survive → nodes die instantly while the API
  reports "started". Found by reading EVE-NG source; fixed in startup.sh
  (wipe stale state, start nodes individually).
- **Lesson**: repo is the network's source of truth — config changes go
  into configs/ + rebuild, not live pushes; live state evaporates.

## 8. Likely questions, one-line answers

- *Stop it running `reload`?* — "Enforcement point is run_tool() in my
  code, not the prompt; production = command allowlist there."
- *Hallucination?* — "Prompt demands evidence before conclusions; every
  claim traces to logged command output; it refused to guess when
  devices were unreachable — I have the transcript."
- *Why not fine-tune?* — "Frontier models already know IOS; the
  engineering is tools, guardrails, context."
- *Cost?* — "2–4 model calls per diagnosis; seconds and cents vs human
  NOC time."
- *What's next for the lab?* — endpoints in the VLANs, upstream ISP + 
  HSRP for real failover demos, syslog→Splunk MCP so the agent is
  event-driven, NETCONF writes behind approval gates.
