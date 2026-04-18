# WIGO Deployment & Certificate Management

WIGO uses mutual TLS (mTLS) for all Agent-to-Controller communication. The Controller acts as a Private Certificate Authority (CA).

## 1. Quick Start with Docker Compose
The easiest way to run the WIGO Controller is using Docker Compose:

1. **Set Environment Variables**: Create a `.env` file or export your Gemini API Key:
   ```bash
   echo "GEMINI_API_KEY=your_key_here" > .env
   ```
2. **Build and Start**:
   ```bash
   docker-compose up -d --build
   ```
3. **Verify**: 
   - Management: `http://localhost:5000/health`
   - Agent API: `https://localhost:8443/health`

## 2. Controller Architecture
- **Management (Port 5000)**: HTTP only. Used for GUI, configuration, and AI action approvals.
- **Agent API (Port 8443)**: HTTPS with mTLS. Used for telemetry and instruction polling.

## 2. Agent Onboarding (The Handshake)
1. **Generate CSR**: Agents generate a private key and a Certificate Signing Request (CSR).
2. **Register**: The agent sends the CSR and metadata to `/api/register`.
3. **Install Certs**: The Controller returns the signed certificate and the Root CA. The agent saves these locally.
4. **Burst Mode**: Agents should send telemetry in 15-minute bursts to `/api/actions/telemetry`.

## 3. Remote Proxy Agents (Docker)
For devices like MikroTik that cannot run Python scripts:
1. Ensure the Controller has access to `/var/run/docker.sock`.
2. The Orchestrator will automatically spin up proxy containers based on the `wigo-proxy-mikrotik` image.
3. These containers will poll the hardware via SSH and forward telemetry to the Controller.

# COMMANDS.md: AI Action Schema

The WIGO "Brain" generates structured actions based on telemetry analysis.

## Action Proposal Format
The LLM responds with:
```json
{
    "issue_detected": true,
    "rationale": "High CPU load detected on router due to BGP churn.",
    "proposed_command": "RESTART_BGP_SERVICE",
    "severity": "HIGH"
}
```

## Supported Commands (Examples)
- `RESTART_SERVICE [name]`: Restarts a service on the agent.
- `BLOCK_IP [ip]`: Adds a firewall rule to block a specific IP.
- `LOG_FLUSH`: Clears temporary logs.
- `CUSTOM [shell_command]`: Runs a custom command (requires additional permission).

## Human-in-the-Loop Approval
All actions start in `PENDING` status. To execute:
1. The user receives a notification with an `approval_url`.
2. The user (or an automation) calls `POST /api/actions/{id}/approve?token={token}`.
3. The next time the Agent polls `/api/actions/pending`, it receives the approved command.
