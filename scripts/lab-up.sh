#!/usr/bin/env bash
# lab-up.sh — bring the whole lab up from the Mac with one command.
#
#   scripts/lab-up.sh              # starts the GCP VM via gcloud, then everything else
#   scripts/lab-up.sh <vm-ip>      # VM already started (e.g. from the console)? skip gcloud
#
# Steps: start VM -> get external IP -> wait for SSH -> sync repo code to VM
#        -> run startup.sh (starts EVE-NG lab, bridge, MCP, waits for devices)
set -euo pipefail

VM_NAME="eve-ng-lab"
VM_USER="ayethandaraung"
SSH_KEY="$HOME/.ssh/google_compute_engine"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5)

# ── Step 1: start the VM and learn its external IP ─────────────────────
if [ $# -ge 1 ]; then
    VM_IP="$1"
    echo "[1/4] Using provided VM IP: $VM_IP"
else
    if ! command -v gcloud >/dev/null 2>&1; then
        echo "gcloud is not installed. Either:"
        echo "  a) install it once:   brew install --cask google-cloud-sdk"
        echo "     then login:        gcloud auth login"
        echo "  b) or start the VM in the GCP console and re-run with the IP:"
        echo "     scripts/lab-up.sh <external-ip>"
        exit 1
    fi
    ZONE=$(gcloud compute instances list --filter="name=$VM_NAME" --format="value(zone)")
    if [ -z "$ZONE" ]; then
        echo "ERROR: instance '$VM_NAME' not found — check 'gcloud config set project <id>'"
        exit 1
    fi
    echo "[1/4] Starting $VM_NAME in $ZONE..."
    gcloud compute instances start "$VM_NAME" --zone="$ZONE" >/dev/null
    VM_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" \
            --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    echo "      External IP: $VM_IP"
fi

# ── Step 2: wait for SSH ───────────────────────────────────────────────
echo "[2/4] Waiting for SSH on $VM_IP..."
for i in $(seq 1 30); do
    if ssh "${SSH_OPTS[@]}" "$VM_USER@$VM_IP" true 2>/dev/null; then
        echo "      SSH is up."
        break
    fi
    [ "$i" -eq 30 ] && { echo "ERROR: SSH never came up"; exit 1; }
    sleep 5
done

# ── Step 3: sync repo code to the VM ───────────────────────────────────
echo "[3/4] Syncing code to VM..."
rsync -a -e "ssh ${SSH_OPTS[*]}" \
    "$REPO_DIR/agent.py" "$REPO_DIR/tools.py" "$REPO_DIR/simulator.py" \
    "$REPO_DIR/startup.sh" "$REPO_DIR/prompts" "$REPO_DIR/mcp" \
    "$REPO_DIR/topology" \
    "$VM_USER@$VM_IP:/opt/network-mcp/"
echo "      Code synced."

# ── Step 4: run startup.sh on the VM ───────────────────────────────────
echo "[4/4] Running startup.sh on the VM (lab boot takes ~3 min)..."
ssh "${SSH_OPTS[@]}" "$VM_USER@$VM_IP" "bash /opt/network-mcp/startup.sh"

echo ""
echo "================================================"
echo " Lab is up.  VM IP: $VM_IP"
echo ""
echo " Agent on the VM:   ssh -i $SSH_KEY $VM_USER@$VM_IP"
echo "                    cd /opt/network-mcp && venv/bin/python3 agent.py"
echo " Claude Desktop:    set JUMP_HOST=$VM_IP in the network-ops server env"
echo "                    (remove USE_SIMULATOR), then restart Claude Desktop"
echo " Sync reports:      scripts/sync-reports.sh $VM_IP"
echo "================================================"
