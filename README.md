# WIGO - What Is Going On

WIGO is a lightweight, centralized observability system designed for homelabs and infrastructure monitoring. It combines real-time metric collection with AI-driven NOC and SIEM analysis.

## Core Features

- **Centralized Collector**: A FastAPI-based backend that gathers reports from multiple agents.
- **Syslog Server**: Built-in UDP/TCP port 514 listener for network devices.
- **Smart AI Engines**:
  - **NOC Monitor**: Analyzes performance trends and calculates health digests.
  - **SIEM Monitor**: Detects security anomalies and unique error patterns.
- **Drill-Down Capability**: AI can automatically request more troubleshooting data/commands.
- **Automated Notifications**: Integrated with Pushover and Home Assistant for instant alerts.
- **Efficient Storage**: Local log deduplication and configurable data retention.
- **Modern Dashboard**: Responsive UI with glassmorphism aesthetics.

## Project Structure

- `/src/collector`: Backend FastAPI server and AI engines.
- `/agents`: Monitoring scripts for Proxmox, Ubuntu, and MikroTik.
- `/data`: Persistent storage for SQLite DB and configuration.
- `/docker`: Containerization files.

## API Documentation

The Collector exposes a full REST API. Auto-generated docs are available at `/docs`.

### Key Maintenance Endpoints

- `POST /api/maintenance/purge?days=X`: 
  - Purges data older than X days.
  - Set `days=0` to purge everything.
- `GET /api/maintenance/context?machine=NAME_OR_IP`:
  - Returns a text digest of the last 4 hours for AI context.
  - Can be filtered by machine name or IP address.
- `GET /api/maintenance/last-report`: Returns the most recent AI analysis report.
- `POST /api/maintenance/full-cycle-ai`: Runs analysis, sends notifications, and purges data in one go.

## Setup & Deployment

1. **Configure**: Edit `data/config.yaml` with your AI API keys and webhook tokens.
2. **Deploy**:
   ```bash
   docker-compose up -d --build
   ```
3. **Deploy Agents**: Copy scripts from `/agents` to your target machines and set them as cron jobs.

## AI Optimization
WIGO uses "Health Digests" to reduce token usage:
- Metrics are sent as Min/Max/Avg aggregates.
- Logs are deduplicated and ranked to prioritize errors over routine events.
- AI can return JSON commands to request further "drill-down" data if needed.
