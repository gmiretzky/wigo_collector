#!/bin/bash

# WIGO Proxmox Agent Un-installation Script
# Must be run as root

set -e

echo "Starting WIGO Proxmox Agent Un-installation..."

# 1. Stop and Disable Service
if systemctl is-active --quiet wigo-proxmox; then
    echo "Stopping wigo-proxmox service..."
    systemctl stop wigo-proxmox
fi

if systemctl is-enabled --quiet wigo-proxmox; then
    echo "Disabling wigo-proxmox service..."
    systemctl disable wigo-proxmox
fi

# 2. Remove Systemd Service
echo "Removing systemd service unit..."
rm -f /etc/systemd/system/wigo-proxmox.service
systemctl daemon-reload

# 3. Remove Binary and Config
echo "Removing agent files..."
rm -f /usr/local/bin/wigo-proxmox.py
rm -rf /etc/wigo

# 4. Remove Sudoers Config
echo "Removing sudoers configuration..."
rm -f /etc/sudoers.d/wigo

# 5. Remove Logs
echo "Removing logs..."
rm -rf /var/log/wigo

# 6. Remove WIGO User
if id "wigo" &>/dev/null; then
    echo "Removing wigo user and home directory..."
    userdel -r wigo || echo "Warning: Could not fully remove wigo user home."
fi

echo "----------------------------------------------------"
echo "Un-installation Complete!"
echo "The WIGO Proxmox Agent has been fully removed."
echo "----------------------------------------------------"
