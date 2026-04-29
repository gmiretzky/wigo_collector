#!/bin/bash

# WIGO Proxmox Agent Installation & Update Script
# Must be run as root on a Proxmox VE host

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <git_repo_url>"
    echo "Example: $0 https://github.com/gmiretzky/wigo_collector.git"
    exit 1
fi

GIT_REPO="$1"
AGENT_NAME="proxmox"
SERVICE_NAME="wigo-proxmox.service"
LOCAL_VERSION_FILE="/etc/wigo/version.txt"

echo "Starting WIGO Proxmox Agent Installation/Update..."

if ! command -v git &> /dev/null; then
    echo "Git is not installed. Installing git..."
    apt-get update || true
    apt-get install -y git
fi

# Check if agent is already running/installed
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}"; then
    echo "Agent service is already installed. Checking for updates..."
    LOCAL_VERSION=$(cat $LOCAL_VERSION_FILE 2>/dev/null || echo "0.0")
    
    TEMP_DIR=$(mktemp -d)
    echo "Pulling latest version from Git..."
    git clone --depth 1 "$GIT_REPO" "$TEMP_DIR" > /dev/null 2>&1
    
    REMOTE_VERSION=$(cat "$TEMP_DIR/agents/$AGENT_NAME/version.txt" 2>/dev/null || echo "0.0")
    
    if [ "$LOCAL_VERSION" != "$REMOTE_VERSION" ]; then
        echo "New version found (Local: $LOCAL_VERSION, Remote: $REMOTE_VERSION). Updating..."
        systemctl stop "$SERVICE_NAME"
        
        # Copy updated files
        cp "$TEMP_DIR/agents/$AGENT_NAME/wigo-proxmox.py" /usr/local/bin/wigo-proxmox.py
        cp "$TEMP_DIR/agents/$AGENT_NAME/version.txt" "$LOCAL_VERSION_FILE"
        
        chown wigo:wigo /usr/local/bin/wigo-proxmox.py
        chmod +x /usr/local/bin/wigo-proxmox.py
        
        # Update python dependencies
        sudo -u wigo /home/wigo/venv/bin/pip install httpx cryptography pyyaml psutil > /dev/null 2>&1
        
        systemctl start "$SERVICE_NAME"
        echo "Version changed from $LOCAL_VERSION to $REMOTE_VERSION."
    else
        echo "Version has not changed (Version: $LOCAL_VERSION). No update needed."
    fi
    
    rm -rf "$TEMP_DIR"
    exit 0
fi

echo "New setup. Installing agent..."

# 0. Clone repository
TEMP_DIR=$(mktemp -d)
echo "Pulling agent files from Git..."
git clone --depth 1 "$GIT_REPO" "$TEMP_DIR" > /dev/null 2>&1

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
cp "$TEMP_DIR/agents/$AGENT_NAME/wigo-proxmox.py" /usr/local/bin/wigo-proxmox.py
cp "$TEMP_DIR/agents/$AGENT_NAME/config.yaml" /etc/wigo/config.yaml
cp "$TEMP_DIR/agents/$AGENT_NAME/version.txt" "$LOCAL_VERSION_FILE"

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

rm -rf "$TEMP_DIR"

echo "----------------------------------------------------"
echo "Setup completed for new installation."
echo "Please edit /etc/wigo/config.yaml with your token."
echo "Then start the service with: systemctl start wigo-proxmox"
echo "----------------------------------------------------"
