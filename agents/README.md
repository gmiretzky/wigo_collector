# WIGO Agent Building Guidelines

This document outlines the standard requirements for creating new WIGO agent types. Each agent type must be contained within its own subdirectory in the `agents/` folder.

## Required File Structure
Each agent subdirectory (e.g., `agents/proxmox/`) should include:

1.  **Main Agent Script:** The core logic (e.g., `wigo-agent.py`, `wigo-proxmox.py`).
2.  **config.yaml:** A configuration file containing at least:
    *   `controller_url`: The URL of the WIGO Controller.
    *   `registration_token`: The token generated during manual registration.
    *   `hostname`: The machine's hostname.
3.  **setup.sh:** An automated installation script that:
    *   Checks for dependencies.
    *   Configures the environment.
    *   Sets up the agent as a system service (e.g., systemd).
4.  **uninstall.sh:** A script to cleanly remove the agent and its configuration from the host.

## Development Workflow
1.  **Create Directory:** Create a new folder in `agents/` named after the target OS or platform (e.g., `agents/mikrotik`).
2.  **Implement Collection Logic:** The agent must collect system metrics (CPU, RAM, Uptime) and logs, then post them to the Controller's agent API on port 8443 (via mTLS).
3.  **Registration Loop:** The agent should support an initial registration phase using the token provided by the Controller dashboard.
4.  **Service Integration:** Ensure the agent restarts automatically on boot.

## Documentation
Each agent folder should contain its own `README.md` explaining platform-specific installation steps (e.g., RouterOS commands for MikroTik).
