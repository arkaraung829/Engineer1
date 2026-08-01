#!/bin/bash
# setup-gcp-vm.sh
# Run this on YOUR MAC to create the GCP VM.
# Prerequisites: gcloud CLI installed and authenticated
#
# Install gcloud CLI first if you don't have it:
#   brew install --cask google-cloud-sdk
#   gcloud auth login
#   gcloud config set project YOUR_PROJECT_ID

# ─────────────────────────────────────────────
# CONFIGURATION — change these if needed
# ─────────────────────────────────────────────
PROJECT_ID="network-ai-lab-001"
ZONE="us-central1-a"                  # change to region closest to you
VM_NAME="eve-ng-lab"
MACHINE_TYPE="n2-standard-4"          # 4 vCPU / 16GB — n2 guaranteed nested virt
DISK_SIZE="80GB"
DISK_TYPE="pd-ssd"

echo "================================================"
echo " EVE-NG Lab Setup on GCP"
echo "================================================"
echo "Project:  $PROJECT_ID"
echo "Zone:     $ZONE"
echo "VM Name:  $VM_NAME"
echo "Machine:  $MACHINE_TYPE (4 vCPU / 16GB RAM)"
echo "Disk:     $DISK_SIZE SSD"
echo ""

# Set the project
GCLOUD=/Users/ayethandaraung/google-cloud-sdk/bin/gcloud
$GCLOUD config set project $PROJECT_ID

# ─────────────────────────────────────────────
# STEP 1: Create firewall rules
# ─────────────────────────────────────────────
echo "[1/3] Creating firewall rules..."

# Allow SSH from your IP
$GCLOUD compute firewall-rules create eve-ng-ssh \
  --allow tcp:22 \
  --target-tags=eve-ng \
  --description="SSH access to EVE-NG" \
  --quiet 2>/dev/null || echo "  SSH rule already exists, skipping"

# Allow EVE-NG web UI (HTTP + HTTPS)
$GCLOUD compute firewall-rules create eve-ng-web \
  --allow tcp:80,tcp:443 \
  --target-tags=eve-ng \
  --description="EVE-NG web UI" \
  --quiet 2>/dev/null || echo "  Web rule already exists, skipping"

# Allow VNC for device consoles
$GCLOUD compute firewall-rules create eve-ng-vnc \
  --allow tcp:5900-6000 \
  --target-tags=eve-ng \
  --description="VNC console access" \
  --quiet 2>/dev/null || echo "  VNC rule already exists, skipping"

echo "  Firewall rules ready."

# ─────────────────────────────────────────────
# STEP 2: Create boot disk with nested virt enabled
# ─────────────────────────────────────────────
echo ""
echo "[2/3] Creating boot disk with nested virtualization..."

# Create the disk first
$GCLOUD compute disks create ${VM_NAME}-disk \
  --zone=$ZONE \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --size=$DISK_SIZE \
  --type=$DISK_TYPE \
  --quiet

# Create custom image with nested virtualization license
$GCLOUD compute images create ${VM_NAME}-image \
  --source-disk=${VM_NAME}-disk \
  --source-disk-zone=$ZONE \
  --licenses="https://www.googleapis.com/compute/v1/projects/vm-options/global/licenses/enable-vmx" \
  --quiet

echo "  Boot disk ready with nested virtualization enabled."

# ─────────────────────────────────────────────
# STEP 3: Create the VM
# ─────────────────────────────────────────────
echo ""
echo "[3/3] Creating VM (spot instance)..."

$GCLOUD compute instances create $VM_NAME \
  --zone=$ZONE \
  --machine-type=$MACHINE_TYPE \
  --image=${VM_NAME}-image \
  --tags=eve-ng \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --quiet

echo ""
echo "================================================"
echo " VM Created Successfully!"
echo "================================================"

# Get the external IP
EXTERNAL_IP=$($GCLOUD compute instances describe $VM_NAME \
  --zone=$ZONE \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "External IP: $EXTERNAL_IP"
echo ""
echo "Next steps:"
echo "  1. SSH into the VM:"
echo "     gcloud compute ssh $VM_NAME --zone=$ZONE"
echo ""
echo "  2. Upload the EVE-NG install script:"
echo "     gcloud compute scp lab/install-eve-ng.sh $VM_NAME:~ --zone=$ZONE"
echo ""
echo "  3. Run the install script inside the VM:"
echo "     bash install-eve-ng.sh"
echo ""
echo "  4. Access EVE-NG web UI at:"
echo "     http://$EXTERNAL_IP"
echo "     Username: admin"
echo "     Password: eve"
echo ""
echo "IMPORTANT — Save these details:"
echo "  VM Name:     $VM_NAME"
echo "  External IP: $EXTERNAL_IP"
echo "  Zone:        $ZONE"
echo ""
echo "To STOP the VM (stop billing):"
echo "  gcloud compute instances stop $VM_NAME --zone=$ZONE"
echo ""
echo "To START the VM again:"
echo "  gcloud compute instances start $VM_NAME --zone=$ZONE"
echo ""
echo "To DELETE the VM completely:"
echo "  gcloud compute instances delete $VM_NAME --zone=$ZONE"
