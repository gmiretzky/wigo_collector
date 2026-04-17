# WIGO (What Is Going On)

WIGO is a lightweight, centralized monitoring and AI-analysis system designed for homelabs and infrastructure. It provides a unified observability layer with automated AI insights for both Performance (NOC) and Security (SIEM).

## Features

- **Centralized Collector**: Dockerized FastAPI service with SQLite backend.
- **Modern Dashboard**: Premium, dark-mode, glassmorphism UI for real-time status.
- **Dual AI Operations**:
  - **NOC Monitor**: Analyzes performance trends (CPU, RAM, Disk) every 4 hours.
  - **SIEM Monitor**: Analyzes logs for security anomalies and threats.
- **Syslog Server**: Built-in UDP/TCP port 514 listener to receive logs from network devices.
- **Flexible AI Providers**: Built-in support for **Google Gemini** and local **Ollama**.
- **Dynamic Integrations**: Configure Pushover, Home Assistant, or custom webhooks via the API/GUI.
- **Threshold Alarms**: Immediate notifications for critical metrics (e.g., CPU > 95%).
- **Swagger API**: Full programmatic control via `/docs`.

## Directory Structure

- `/docker`: Docker Compose and Dockerfile configuration.
- `/src/collector`: Backend FastAPI source code.
- `/data`: Persistent storage for database and configuration (mapped to volume).
- `/agents`: Distributed scripts for Proxmox, Ubuntu, and MikroTik.

## Setup Instructions

### 1. Deploy the Collector

Ensure you have Docker and Docker Compose installed.

```bash
cd docker
docker-compose up -d --build
```

The dashboard will be available at `http://localhost:5000`.
The API documentation is at `http://localhost:5000/docs`.

### 2. Configure the System

Edit `data/config.yaml` or use the API/GUI to set:
- AI API Keys (Gemini/Ollama).
- Thresholds for alerts.
- Webhook tokens for Pushover/Home Assistant.

### 3. Deploy Agents

#### Proxmox Agent
1. Copy `agents/proxmox/wigo_proxmox.py` to your Proxmox node.
2. Edit the `COLLECTOR_URL` in the script.
3. Install dependencies: `pip install requests` (or use a venv).
4. Add to crontab: `*/5 * * * * /usr/bin/python3 /path/to/wigo_proxmox.py`

#### Ubuntu Agent
1. Copy `agents/ubuntu/wigo_ubuntu.py` to your server.
2. Edit the `COLLECTOR_URL`.
3. Add to crontab: `*/5 * * * * /usr/bin/python3 /path/to/wigo_ubuntu.py`

#### MikroTik Agent
1. Import `agents/mikrotik/wigo_mikrotik.rsc` into your RouterOS.
2. Update the `collectorUrl` in the script.
3. Schedule the script in `/system scheduler`.

## AI Analysis Strategy

WIGO uses **Bulk Processing** to optimize token usage and context awareness. Instead of analyzing every heartbeat, it aggregates data every 4 hours and sends a "State of the Union" report to the AI.

- **NOC Analysis**: Looks for slow climbs in usage, potential bottlenecks, and capacity planning.
- **SIEM Analysis**: Scans logs for brute-force attempts, unauthorized access, or unusual system behavior.
