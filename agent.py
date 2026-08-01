# agent.py
# The main orchestrator — ties together Claude, tools, memory, and goals.
#
# Architecture reminder:
#   USER → ORCHESTRATOR → CLAUDE → TOOLS → DEVICES → back to CLAUDE → USER

import anthropic
import json
import os
from tools import ssh_exec, save_report

client = anthropic.Anthropic()

# ─────────────────────────────────────────────
# MEMORY FILE — persists conversation across sessions
# ─────────────────────────────────────────────
MEMORY_FILE = "memory/conversation.json"


def load_memory() -> list:
    """Load previous conversation from disk."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return []


def save_memory(messages: list):
    """Save conversation to disk so next session remembers it."""
    os.makedirs("memory", exist_ok=True)
    # Only save text messages (not tool call objects — they can't serialize)
    saveable = []
    for msg in messages:
        if isinstance(msg["content"], str):
            saveable.append(msg)
        elif isinstance(msg["content"], list):
            # Only keep text blocks from assistant messages
            text_blocks = [b for b in msg["content"] if isinstance(b, dict) and b.get("type") == "text"]
            if text_blocks:
                saveable.append({"role": msg["role"], "content": text_blocks[0]["text"]})
    with open(MEMORY_FILE, "w") as f:
        json.dump(saveable, f, indent=2)


def clear_memory():
    """Wipe conversation history."""
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
    print("Memory cleared.")


# ─────────────────────────────────────────────
# TOOL DEFINITIONS
# ─────────────────────────────────────────────
TOOLS = [
    {
        "name": "ssh_exec",
        "description": (
            "Run a Cisco IOS show command on a network device via SSH. "
            "Use this to check BGP status, interface status, routing table, "
            "system logs, CPU, memory, and any other network state. "
            "Always use this to gather data before drawing conclusions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "IP address of the Cisco device (e.g. '192.168.0.10')"
                },
                "command": {
                    "type": "string",
                    "description": "The IOS show command to run (e.g. 'show ip bgp summary')"
                }
            },
            "required": ["host", "command"]
        }
    },
    {
        "name": "save_report",
        "description": (
            "Save a diagnosis report to a file. "
            "Call this at the end of every investigation to save findings. "
            "Use markdown with sections: Summary, Root Cause, Evidence, Fix Commands."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The full report content in markdown format"
                },
                "filename": {
                    "type": "string",
                    "description": "Optional filename. Auto-generated if not provided."
                }
            },
            "required": ["content"]
        }
    }
]


def load_system_prompt() -> str:
    with open("prompts/network-agent.md", "r") as file:
        return file.read()


def run_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "ssh_exec":
        return ssh_exec(host=tool_input["host"], command=tool_input["command"])
    if tool_name == "save_report":
        return save_report(content=tool_input["content"], filename=tool_input.get("filename", ""))
    return f"Unknown tool: {tool_name}"


# ─────────────────────────────────────────────
# AGENT LOOP
# ─────────────────────────────────────────────
def ask_agent(question: str, messages: list) -> tuple:
    """
    Send a question to the agent.
    Returns (answer, updated_messages) so memory carries forward.
    """

    # Add the new question to existing conversation history
    messages.append({"role": "user", "content": question})

    print(f"\n{'='*60}")
    print(f"QUESTION: {question}")
    print(f"{'='*60}")

    loop_count = 0

    while True:
        loop_count += 1
        print(f"\n[Loop {loop_count}] Asking Claude...")

        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=4096,
            system=load_system_prompt(),
            tools=TOOLS,
            messages=messages,
            thinking={"type": "adaptive"}
        )

        if response.stop_reason == "end_turn":
            print(f"\n[Loop {loop_count}] Claude finished.")
            answer = ""
            for block in response.content:
                if hasattr(block, "text"):
                    answer = block.text
            # Add Claude's final answer to memory
            messages.append({"role": "assistant", "content": answer})
            return answer, messages

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n[Loop {loop_count}] Claude is calling: {block.name}")
                    print(f"  Input: {block.input}")
                    result = run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\nNetwork AI Agent — Cisco IOS Troubleshooter")
    print("Powered by claude-opus-4-8 + Netmiko")
    print("Commands: 'exit' to quit | 'clear memory' to reset history\n")

    # Load previous conversation from disk
    messages = load_memory()

    if messages:
        print(f"Loaded {len(messages)} messages from previous session.")
    else:
        print("Starting fresh session.")

    while True:
        question = input("\nDescribe the network problem: ").strip()

        if not question:
            continue

        if question.lower() == "exit":
            print("Goodbye.")
            break

        if question.lower() == "clear memory":
            clear_memory()
            messages = []
            continue

        diagnosis, messages = ask_agent(question, messages)

        print(f"\n{'='*60}")
        print("DIAGNOSIS & RECOMMENDED FIX:")
        print(f"{'='*60}")
        print(diagnosis)

        # Save after every question
        save_memory(messages)
