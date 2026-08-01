# AI Agent for Network Infrastructure — Study Guide

```
╔══════════════════════════════════════════════════════════════════╗
║              AI AGENT FOR NETWORK INFRASTRUCTURE                 ║
╚══════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────┐
│                        USER / TRIGGER                           │
│          (you type, or alert fires, or schedule runs)           │
└───────────────────────────┬─────────────────────────────────────┘
                            │  plain English
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                               │
│                      (Python script)                            │
│                                                                 │
│  Loads:  CLAUDE.md          ← rules for Claude Code            │
│          network-agent.md   ← agent persona + goals            │
│          messages[]         ← conversation memory               │
└───────────────────────────┬─────────────────────────────────────┘
                            │  API call
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLAUDE (LLM)                                 │
│                  claude-opus-4-8                                │
│                                                                 │
│   Receives:  system prompt (goals + rules)                      │
│              memory (previous messages)                         │
│              tool definitions (what tools exist)                │
│              user message (the question)                        │
│                                                                 │
│   Thinks:    what do I need to check?                           │
│              which tool should I call?                          │
│              what does the output mean?                         │
└──────┬──────────────────────────────────────────────────────────┘
       │  decides to call a tool
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TOOLS LAYER                                │
│                                                                 │
│   Option A: Custom Python functions                             │
│   ┌──────────────┬──────────────┬──────────────┐               │
│   │  ssh_exec()  │ snmp_query() │ get_config() │               │
│   │  (Netmiko)   │  (pysnmp)    │  (Napalm)    │               │
│   └──────────────┴──────────────┴──────────────┘               │
│                                                                 │
│   Option B: MCP Server  (JSON-RPC protocol)                     │
│   ┌─────────────────────────────────────────┐                  │
│   │  network-ops-mcp  (Python or TypeScript) │                  │
│   │  exposes same tools as above             │                  │
│   │  reusable by Claude Desktop, Claude Code │                  │
│   └─────────────────────────────────────────┘                  │
└──────┬──────────────────────────────────────────────────────────┘
       │  executes against real devices
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NETWORK DEVICES                              │
│                                                                 │
│   Cisco IOS/IOS-XE  ──── SSH (port 22)                         │
│   SNMP agents       ──── UDP 161                               │
│   Syslog            ──── UDP 514                               │
│   NetBox/IPAM       ──── REST API                              │
│   Prometheus/SNMP   ──── Metrics                               │
└──────┬──────────────────────────────────────────────────────────┘
       │  raw output (show commands, OIDs, logs)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BACK TO CLAUDE                                 │
│                                                                 │
│   Interprets output → reasons → calls next tool OR             │
│   concludes → writes answer in plain English → returns to user  │
└─────────────────────────────────────────────────────────────────┘


╔══════════════════════════════════════════════════════════════════╗
║                    THE 5 COMPONENTS                             ║
║              (memorize this — it's the NANOG diagram)           ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  MEMORY     ──► what Claude remembers  = messages[] + CLAUDE.md ║
║  TOOLS      ──► what Claude can do     = ssh, snmp, config, ping║
║  GOALS      ──► what Claude should do  = system prompt (.md)   ║
║  DATA       ──► what Claude reads      = device output, logs   ║
║  GUARDRAILS ──► what Claude can't do   = allowlist, rules      ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════╗
║                  FILE / FOLDER STRUCTURE                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Engineer1/                                                      ║
║  ├── CLAUDE.md              ← Claude Code reads this first      ║
║  ├── AI-AGENT-ARCHITECTURE.md  ← this file                     ║
║  ├── prompts/                                                    ║
║  │   └── network-agent.md  ← agent goals + persona             ║
║  ├── tools/                                                      ║
║  │   ├── ssh_tool.py       ← Netmiko SSH wrapper               ║
║  │   ├── snmp_tool.py      ← pysnmp wrapper                    ║
║  │   └── config_tool.py    ← Napalm config fetch               ║
║  ├── mcp/                                                        ║
║  │   └── network-ops-mcp/  ← MCP server (reusable)             ║
║  ├── runbooks/                                                   ║
║  │   └── bgp-down.md       ← Claude reads during diagnosis     ║
║  └── agent.py              ← main orchestrator                  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════╗
║                    LANGUAGES (priority order)                   ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  1. Python      ── orchestrator, tools, MCP server              ║
║  2. Markdown    ── CLAUDE.md, prompts, runbooks (AI config)     ║
║  3. JSON        ── tool definitions, API wire format            ║
║  4. YAML        ── device inventory, Ansible, configs           ║
║  5. Bash        ── local diagnostics, shell commands            ║
║  6. TypeScript  ── MCP server (optional, Anthropic-preferred)   ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════╗
║                  HOW A REQUEST FLOWS (8 steps)                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  1. User asks: "Why is BGP down on core-router-01?"             ║
║  2. Orchestrator loads memory + goals, calls Claude API         ║
║  3. Claude decides: call ssh_exec("show bgp summary")           ║
║  4. Tool SSHs to device, returns raw output                     ║
║  5. Claude reads output, decides: call ssh_exec("show log")     ║
║  6. Claude reads log, finds root cause                          ║
║  7. Claude returns plain English answer + fix commands          ║
║  8. User applies fix (or agent applies it automatically)        ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════╗
║              OUR STACK vs CISCO IQ vs NANOG DIAGRAM             ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  NANOG Term        │ Our Stack              │ Cisco IQ           ║
║  ──────────────────┼────────────────────────┼────────────────────║
║  LLM               │ claude-opus-4-8        │ Proprietary ML     ║
║  Memory            │ messages[] + CLAUDE.md │ Cisco telemetry DB ║
║  Tools             │ ssh, snmp, napalm, mcp │ Fixed Cisco tools  ║
║  Goals             │ network-agent.md       │ Fixed rules        ║
║  Data              │ your devices, live     │ Cisco cloud data   ║
║  Guardrails        │ your allowlist         │ Cisco controls     ║
║  Vendor support    │ Any (Cisco/Junos/Linux)│ Cisco only         ║
║  Customizable      │ Fully                  │ No                 ║
║  Conversational    │ Yes                    │ No                 ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════╗
║                    KEY TERMS TO KNOW                            ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  LLM          Large Language Model — the AI brain (Claude)      ║
║  Agent        LLM + tools + memory + goals acting autonomously  ║
║  Tool         Function Claude can call to interact with world   ║
║  MCP          Model Context Protocol — standard way to share    ║
║               tools across Claude Desktop, Code, custom apps    ║
║  Orchestrator Your Python code that manages the agent loop      ║
║  Tool loop    Claude calls tool → gets result → calls next tool ║
║  Guardrails   Rules that prevent Claude from doing unsafe things║
║  Netmiko      Python library for SSH to network devices         ║
║  Napalm       Python library for multi-vendor config management ║
║  pysnmp       Python library for SNMP queries                   ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

echo 'export ANTHROPIC_API_KEY="your-key-here"' >> ~/.bashrc
