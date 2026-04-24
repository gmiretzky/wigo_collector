# WIGO - What Is Going On

WIGO is a lightweight, centralized observability system designed for homelabs and infrastructure monitoring. It combines real-time metric collection with AI-driven NOC and SIEM analysis, now featuring enhanced Ubuntu Agent management and token-based identity verification.

## Core Features

- **Centralized Controller**: A FastAPI-based backend that manages agents and gathers telemetry.
- **Secure Onboarding**: Token-based handshake for new agents with mTLS certificate signing.
- **Ubuntu Agent Management**: Integrated management for Ubuntu nodes with automated instruction polling.
- **Intent-to-Action Engine**: 
  - Global Chat: Input intent (e.g., "Fix disk space on all Linux servers") -> AI translates to actions across multiple agents.
  - Command Whitelisting: Validates all AI commands against a `SAFE_COMMANDS` list with permission levels.
- **Recursive Action Loop**: 
  - AI analyzes results and automatically issues follow-up commands (up to 3 iterations).
  - Human-in-the-loop: State-changing actions (Level 2) require user approval.
- **Audit Logs**: Detailed `c2_audit.log` for full traceability of AI reasoning and user intent.
- **Modern Dashboard**: Responsive UI with glassmorphism aesthetics, featuring "Add Agent" workflows and history views.

## Project Structure

- `/src/wigo`: Backend FastAPI server, AI engines, and web management interface.
- `/agents`: Monitoring scripts and local agents for Proxmox, Ubuntu, and MikroTik.
- `/data`: Persistent storage for SQLite DB and configuration.
- `/docker`: Containerization files for the Controller and Proxy Agents.

## API Documentation

The Controller exposes a full REST API. Auto-generated docs are available at `/docs`.

### Key Endpoints

- `POST /api/dashboard/pre-register`: Generates a registration token for a new agent.
- `POST /api/registration/register`: Signs a CSR and registers an agent (requires valid token).
- `GET /api/actions/history`: Retrieves the history of all actions and their results.
- `POST /api/actions/{id}/result`: Allows agents to report the outcome of an executed command.

## Setup & Deployment

1. **Configure**: Set the `GEMINI_API_KEY` environment variable (required for the Intent-to-Action engine).
2. **Deploy**:
   ```bash
   GEMINI_API_KEY=your_key_here docker-compose up -d --build
   ```
3. **Add Agent**:
   - Open the Management Dashboard (Port 5000).
   - Click "Add Agent", enter the hostname and IP.
   - Use the generated **Registration Token** to onboard your new agent.

## AI Optimization & Observability
WIGO uses "Health Digests" to reduce token usage and improve analysis:
- Metrics are sent as Min/Max/Avg aggregates.
- Logs are deduplicated and ranked to prioritize errors over routine events.
- **Action Loop**: AI analyzes the results of executed commands to verify if the issue was resolved or if further action is required.
