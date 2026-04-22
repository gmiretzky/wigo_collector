#!/bin/bash

# WIGO Proxmox Agent Installation Script
# Must be run as root on a Proxmox VE host

set -e

echo "Starting WIGO Proxmox Agent Installation..."

# 1. Install Dependencies
echo "Installing dependencies..."
# We ignore errors here because Proxmox hosts often have the enterprise repo enabled without a subscription,
# which causes 'apt-get update' to return a 401 error.
apt-get update || true
apt-get install -y python3 python3-pip python3-venv sudo || {
    echo "ERROR: Failed to install dependencies. Please ensure your Debian repositories are reachable."
    exit 1
}

# 2. Create WIGO User
if ! id "wigo" &>/dev/null; then
    echo "Creating wigo user..."
    useradd -m -s /bin/bash wigo
fi

# 3. Setup Directories
echo "Setting up directories..."
mkdir -p /etc/wigo/certs
mkdir -p /var/log/wigo
chown -R wigo:wigo /etc/wigo
chown -R wigo:wigo /var/log/wigo

# 4. Sudoers Configuration
echo "Configuring sudoers for Proxmox CLI access..."
cat <<EOF > /etc/sudoers.d/wigo
wigo ALL=(ALL) NOPASSWD: /usr/sbin/qm *
wigo ALL=(ALL) NOPASSWD: /usr/sbin/pct *
wigo ALL=(ALL) NOPASSWD: /usr/bin/pvesh *
wigo ALL=(ALL) NOPASSWD: /usr/bin/journalctl *
wigo ALL=(ALL) NOPASSWD: /usr/bin/grep *
EOF
chmod 440 /etc/sudoers.d/wigo

# 5. Copy Files
echo "Copying agent files..."
cp wigo-proxmox.py /usr/local/bin/wigo-proxmox.py
cp config.yaml /etc/wigo/config.yaml
chown wigo:wigo /usr/local/bin/wigo-proxmox.py
chown wigo:wigo /etc/wigo/config.yaml
chmod +x /usr/local/bin/wigo-proxmox.py

# 6. Python Environment
echo "Setting up Python environment..."
sudo -u wigo python3 -m venv /home/wigo/venv
sudo -u wigo /home/wigo/venv/bin/pip install httpx cryptography pyyaml psutil

# 7. Systemd Service
echo "Installing systemd service..."
cat <<EOF > /etc/systemd/system/wigo-proxmox.service
[Unit]
Description=WIGO Proxmox Agent
After=network.target

[Service]
Type=simple
User=wigo
WorkingDirectory=/home/wigo
ExecStart=/home/wigo/venv/bin/python3 /usr/local/bin/wigo-proxmox.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable wigo-proxmox

echo "----------------------------------------------------"
echo "Installation Complete!"
echo "Please edit /etc/wigo/config.yaml with your token."
echo "Then start the service with: systemctl start wigo-proxmox"
echo "----------------------------------------------------"
