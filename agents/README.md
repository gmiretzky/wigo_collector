# WIGO Agent Building Guidelines

This document outlines the standard requirements for creating new WIGO agent types. Each agent type must be contained within its own subdirectory in the `agents/` folder.

## Required File Structure
Each agent subdirectory (e.g., `agents/proxmox/`) should include:

1.  **Main Agent Script:** The core logic (e.g., `wigo-agent.py`, `wigo-proxmox.py`).
2.  **config.yaml:** A configuration file containing at least:
    *   `controller_url`: The URL of the WIGO Controller.
    *   `registration_token`: The token generated during manual registration.
    *   `hostname`: The machine's hostname.
3.  **setup.sh:** An automated installation and update script that requires the Git repository URL as an argument (e.g., `./setup.sh https://github.com/gmiretzky/wigo_collector.git`). It:
    *   Checks if the agent is currently running.
    *   If not running: clones the repository, installs dependencies, configures the environment, and sets up the system service.
    *   If running: compares the local `version.txt` with the remote repository. If an update is available, it stops the service, applies the updated files, and restarts it. Note: Only public repositories are supported for automated updates currently (no credentials required).
4.  **uninstall.sh:** A script to cleanly remove the agent and its configuration from the host.
5.  **version.txt:** A file containing the current version number of the agent (e.g., `1.0.0`). Used by `setup.sh` to determine if an update is necessary.

## Development Workflow
1.  **Create Directory:** Create a new folder in `agents/` named after the target OS or platform (e.g., `agents/mikrotik`).
2.  **Implement Collection Logic:** The agent must collect system metrics (CPU, RAM, Uptime) and logs, then post them to the Controller's agent API on port 8443 (via mTLS).
3.  **Registration Loop:** The agent should support an initial registration phase using the token provided by the Controller dashboard.
4.  **Service Integration:** Ensure the agent restarts automatically on boot.

## Command Execution Requirements
Agents must implement a polling loop (default 60s) to fetch pending actions from `/api/actions/pending`.
When executing a command:
- **stdout/stderr:** Must be captured and reported back to `/api/actions/{id}/result`.
- **Exit Codes:** Non-zero exit codes should be reported correctly to allow AI error analysis.
- **Traceability:** Agents must include the `trace_id` provided by the controller in all related log entries.

## Command Whitelisting
The WIGO Controller enforces security via brand-specific command whitelists. 
When building a new agent:
1.  **Define Safe Commands:** Identify which commands are "Read-only" (Level 1) and which are "State-changing" (Level 2).
2.  **Submit Config:** Provide a `<brand>.yaml` file to be placed in the controller's `config/commands/` directory.
    - Example `ubuntu.yaml`:
      ```yaml
      uptime: 1
      df: 1
      reboot: 2
      ```
3.  **Default Behavior:** If no brand-specific config exists, the controller falls back to `generic.yaml` (minimal commands) and defaults unknown commands to Level 2 (Requires Approval).

## Documentation
Each agent folder should contain its own `README.md` explaining platform-specific installation steps and a list of recommended `SAFE_COMMANDS` for the controller.
