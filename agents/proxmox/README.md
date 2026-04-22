# WIGO Proxmox Agent

A high-performance, secure agent designed for Proxmox VE hosts. It collects host and guest (VM/LXC) metrics, monitors logs, and executes management commands via mTLS.

## Features

- **Secure Identity**: Automatic CSR generation and mTLS certificate registration with WIGO Controller.
- **Host Metrics**: CPU, RAM, and Disk usage of the physical node.
- **Guest Metrics**: Status and resource usage of all VMs (QEMU) and Containers (LXC).
- **Log Monitoring**: Specifically targets Proxmox cluster events and migration errors.
- **Execution Engine**:
    - `VM_START:[vmid]`
    - `VM_STOP:[vmid]`
    - `CT_RESTART:[vmid]`
    - `SNAPSHOT_CREATE:[vmid]:[name]`

## Installation

1. **Transfer files** to your Proxmox host:
   ```bash
   scp -r agents/proxmox root@your-proxmox-ip:/tmp/
   ```

2. **Run the setup script** as root:
   ```bash
   cd /tmp/proxmox
   chmod +x setup.sh uninstall.sh
   sudo ./setup.sh
   ```

3. **Configure the agent**:
   Edit `/etc/wigo/config.yaml` and set your `registration_token` and `management_url`.

4. **Start the service**:
   ```bash
   sudo systemctl start wigo-proxmox
   sudo systemctl status wigo-proxmox
   ```

## Security & Permissions

The agent runs as a dedicated `wigo` user. It uses a restricted sudoers fragment in `/etc/sudoers.d/wigo` to execute only necessary Proxmox CLI tools:
- `/usr/sbin/qm`
- `/usr/sbin/pct`
- `/usr/bin/pvesh`
- `/usr/bin/journalctl`
- `/usr/bin/grep`

All VMIDs are validated to be integers before execution to prevent command injection.

## Troubleshooting

### Proxmox Subscription Errors (401 Unauthorized)
If `setup.sh` shows a `401 Unauthorized` error for `enterprise.proxmox.com`, it's because the enterprise repository is enabled without a subscription. The script is designed to ignore this and proceed with standard Debian repositories. 

To fix this on your host and use the Proxmox No-Subscription repository:
1. Disable the enterprise repo:
   ```bash
   sed -i 's/^deb/#deb/g' /etc/apt/sources.list.d/pve-enterprise.list
   ```
2. Add the no-subscription repo (example for trixie):
   ```bash
   echo "deb http://download.proxmox.com/debian/pve trixie pve-no-subscription" > /etc/apt/sources.list.d/pve-install-repo.list
   ```
3. Run `apt-get update` again.

## Un-installation

To remove the agent and all its components:
```bash
sudo /tmp/proxmox/uninstall.sh
```
