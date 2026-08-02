#!/usr/bin/env bash
# Pull agent-generated reports from the GCP VM into the repo.
# Usage: scripts/sync-reports.sh [vm-external-ip]
# The VM's external IP changes when the instance restarts — pass it as an
# argument if the default is stale (check with the GCP console).
set -euo pipefail

VM_IP="${1:-136.114.153.79}"
VM_USER="ayethandaraung"
SSH_KEY="$HOME/.ssh/google_compute_engine"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

rsync -av -e "ssh -i $SSH_KEY" \
    "${VM_USER}@${VM_IP}:/opt/network-mcp/reports/" "${REPO_DIR}/reports/"

echo
echo "Reports synced to ${REPO_DIR}/reports/"
echo "To publish: git add reports/ && git commit -m 'Sync agent reports' && git push"
