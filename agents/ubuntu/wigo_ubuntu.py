import os
import subprocess
import json
import requests
from datetime import datetime, timezone
import socket

# Configuration
COLLECTOR_HOST = "YOUR_COLLECTOR_IP" # Just the IP or Domain
COLLECTOR_PORT = 5000
COLLECTOR_URL = f"http://{COLLECTOR_HOST.rstrip(':')}:{COLLECTOR_PORT}/api/agents/report"
MACHINE_NAME = socket.gethostname()

def get_metrics():
    # CPU
    cpu_load = os.getloadavg()[0]
    
    # RAM
    with open('/proc/meminfo', 'r') as f:
        lines = f.readlines()
        total = int(lines[0].split()[1])
        free = int(lines[1].split()[1])
        ram_pct = 100 * (1 - free / total)

    # Disk
    df = subprocess.check_output(['df', '/']).decode('utf-8').split('\n')[1]
    disk_pct = int(df.split()[4].replace('%', ''))

    return [
        {"object": "CPU Load", "value": round(cpu_load, 2), "unit": "", "status": "ok"},
        {"object": "RAM Usage", "value": round(ram_pct, 1), "unit": "%", "status": "ok"},
        {"object": "Disk Usage", "value": disk_pct, "unit": "%", "status": "ok"}
    ]

def get_logs():
    try:
        # Last 10 lines of syslog or auth.log for SIEM
        output = subprocess.check_output(['tail', '-n', '10', '/var/log/auth.log']).decode('utf-8').split('\n')
        return [line for line in output if line.strip()]
    except:
        return []

def main():
    report = {
        "machine_name": MACHINE_NAME,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": get_metrics(),
        "logs": get_logs()
    }
    
    try:
        requests.post(COLLECTOR_URL, json=report, timeout=10)
    except:
        pass

if __name__ == "__main__":
    main()
