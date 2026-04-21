# WIGO Deployment & Certificate Management

WIGO uses mutual TLS (mTLS) for all Agent-to-Controller communication. The Controller acts as a Private Certificate Authority (CA) and enforces token-based registration for security.

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
   - Management: `http://localhost:5000/`
   - Agent API: `https://localhost:8443/health`

## 2. Controller Architecture
- **Management (Port 5000)**: HTTP only. Used for the Dashboard, configuration, and Action History.
- **Agent API (Port 8443)**: HTTPS with mTLS. Used for telemetry and instruction polling.

## 3. Agent Onboarding (The Handshake)
WIGO now enforces a strict token-based registration process:

1. **Pre-Register**: On the Dashboard, go to "Add Agent". Enter the machine's Hostname and IP.
2. **Get Token**: The Controller generates a unique `registration_token`.
3. **Register**: The Agent sends its CSR, metadata, and the `registration_token` to `/api/registration/register`.
4. **Install Certs**: Upon valid token verification, the Controller signs the CSR and returns the certificate.
5. **Start Telemetry**: The Agent is now authorized to send telemetry and poll for actions.

## 4. Observability & Action Loop
The system implements a closed-loop observability pattern:

1. **Analysis**: AI monitors telemetry and proposes an `Action` (e.g., `RESTART_SERVICE`).
2. **Approval**: User approves the action via the Dashboard or notification link.
3. **Execution**: Agent polls `/api/actions/pending`, receives the command, and executes it.
4. **Reporting**: Agent reports the result (success/failure + logs) to `/api/actions/{id}/result`.
5. **AI Follow-up**: The AI analyzes the reported result to confirm resolution or suggest next steps.

## 5. Remote Proxy Agents (Docker)
For devices like MikroTik that cannot run Python scripts:
1. Ensure the Controller has access to `/var/run/docker.sock`.
2. The Orchestrator spins up proxy containers based on the `wigo-proxy-mikrotik` image.
3. These containers handle the mTLS communication and poll the hardware via SSH.
