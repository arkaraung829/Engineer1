#!/bin/bash
# install-eve-ng.sh
# Run this INSIDE the GCP VM after SSH-ing in.
# Copy to VM with:
#   gcloud compute scp lab/install-eve-ng.sh eve-ng-lab:~ --zone=us-central1-a
# Then SSH in and run:
#   bash install-eve-ng.sh

set -e  # stop script if any command fails

echo "================================================"
echo " EVE-NG Community Edition Installer"
echo " Ubuntu 22.04 on GCP"
echo "================================================"
echo ""

# ─────────────────────────────────────────────
# STEP 1: Verify nested virtualization
# ─────────────────────────────────────────────
echo "[1/5] Checking nested virtualization..."

if grep -q vmx /proc/cpuinfo; then
  echo "  Nested virtualization: ENABLED (Intel VMX found)"
else
  echo "  ERROR: Nested virtualization not detected!"
  echo "  EVE-NG will not work without it."
  echo "  Make sure you used setup-gcp-vm.sh to create this VM."
  exit 1
fi

# ─────────────────────────────────────────────
# STEP 2: Update system
# ─────────────────────────────────────────────
echo ""
echo "[2/5] Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
echo "  System updated."

# ─────────────────────────────────────────────
# STEP 3: Install EVE-NG
# ─────────────────────────────────────────────
echo ""
echo "[3/5] Installing EVE-NG Community Edition..."
echo "  This takes 5-10 minutes..."

# Download and run the official EVE-NG installer
wget -q -O /tmp/eve-ng-install.sh \
  https://www.eve-ng.net/focal/install-eve.sh

bash /tmp/eve-ng-install.sh

echo "  EVE-NG installed."

# ─────────────────────────────────────────────
# STEP 4: Set EVE-NG admin password
# ─────────────────────────────────────────────
echo ""
echo "[4/5] Setting admin password..."

# Default is 'eve' — change this for security
EVE_PASSWORD="eve"
echo "root:$EVE_PASSWORD" | sudo chpasswd
echo "  Password set to: $EVE_PASSWORD"
echo "  Change this after first login!"

# ─────────────────────────────────────────────
# STEP 5: Create folder for device images
# ─────────────────────────────────────────────
echo ""
echo "[5/5] Creating image folders..."

sudo mkdir -p /opt/unetlab/addons/qemu/vios-ADVENTERPRISEK9-M-15.6.1T
sudo mkdir -p /opt/unetlab/addons/qemu/paloalto-10.1.0
sudo chown -R root:root /opt/unetlab/addons/
echo "  Image folders created."
echo "  Upload your IOS and PA-VM images to these folders."

# ─────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────
EXTERNAL_IP=$(curl -s ifconfig.me)

echo ""
echo "================================================"
echo " EVE-NG Installation Complete!"
echo "================================================"
echo ""
echo "Access EVE-NG web UI:"
echo "  URL:      http://$EXTERNAL_IP"
echo "  Username: admin"
echo "  Password: eve"
echo ""
echo "Next steps:"
echo "  1. Open http://$EXTERNAL_IP in your browser"
echo "  2. Login with admin / eve"
echo "  3. Upload Cisco IOSv image to:"
echo "     /opt/unetlab/addons/qemu/vios-ADVENTERPRISEK9-M-15.6.1T/"
echo "  4. Upload PA-VM image to:"
echo "     /opt/unetlab/addons/qemu/paloalto-10.1.0/"
echo "  5. Create your topology in the web UI"
echo ""
echo "To point your agent at EVE-NG devices:"
echo "  Edit tools.py and set USE_SIMULATOR = False"
echo "  Set device IPs to the EVE-NG management IPs"
echo ""
echo "SAVE YOUR WORK — run 'write memory' on Cisco devices"
echo "and 'commit' on PAN-OS before closing sessions."
