#!/usr/bin/env bash
# lab-down.sh — gracefully stop the lab and the GCP VM from the Mac.
# Stops the EVE-NG nodes via the API first (flushes device state), then
# stops the instance. Requires gcloud (installed + authed).
set -euo pipefail

VM_NAME="eve-ng-lab"
VM_USER="ayethandaraung"
SSH_KEY="$HOME/.ssh/google_compute_engine"
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5)

ZONE=$(gcloud compute instances list --filter="name=$VM_NAME" --format="value(zone)")
STATUS=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --format="value(status)")

if [ "$STATUS" != "RUNNING" ]; then
    echo "VM is already $STATUS — nothing to do."
    exit 0
fi

VM_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

echo "[1/2] Stopping lab nodes gracefully on $VM_IP..."
ssh "${SSH_OPTS[@]}" "$VM_USER@$VM_IP" '
    curl -s -c /tmp/c -X POST -H "Content-Type: application/json" \
         -d "{\"username\":\"admin\",\"password\":\"eve\",\"html5\":-1}" \
         http://127.0.0.1/api/auth/login > /dev/null
    curl -s -b /tmp/c http://127.0.0.1/api/labs/redundancy-lab.unl/nodes/stop
    echo' || echo "  (could not stop nodes cleanly — continuing with VM stop)"

echo "[2/2] Stopping VM $VM_NAME..."
gcloud compute instances stop "$VM_NAME" --zone="$ZONE" >/dev/null
echo "VM stopped. Compute billing paused; disk state preserved."
