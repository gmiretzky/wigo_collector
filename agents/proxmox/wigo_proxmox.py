import os
import subprocess
import json
import requests
from datetime import datetime, timezone
import socket

# Configuration - Update these
COLLECTOR_HOST = "YOUR_COLLECTOR_IP" # Just the IP or Domain
COLLECTOR_PORT = 5000
COLLECTOR_URL = f"http://{COLLECTOR_HOST.rstrip(':')}:{COLLECTOR_PORT}/api/agents/report"
MACHINE_NAME = socket.gethostname()

def get_node_metrics():
    # CPU
    cpu_load = os.getloadavg()[0] # 1 min load
    
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
        {"object": "CPU Load", "value": round(cpu_load, 2), "unit": "", "status": "ok" if cpu_load < 4 else "warning"},
        {"object": "RAM Usage", "value": round(ram_pct, 1), "unit": "%", "status": "ok" if ram_pct < 85 else "warning"},
        {"object": "Disk Usage", "value": disk_pct, "unit": "%", "status": "ok" if disk_pct < 90 else "warning"}
    ]

def get_vm_status():
    try:
        output = subprocess.check_output(['qm', 'list']).decode('utf-8').split('\n')[1:-1]
        running = 0
        stopped = 0
        for line in output:
            if 'running' in line:
                running += 1
            else:
                stopped += 1
        return [
            {"object": "VMs Running", "value": running, "unit": "", "status": "ok"},
            {"object": "VMs Stopped", "value": stopped, "unit": "", "status": "ok"}
        ]
    except:
        return []

def get_logs():
    try:
        # Last 10 lines of pveproxy access log
        output = subprocess.check_output(['tail', '-n', '10', '/var/log/pveproxy/access.log']).decode('utf-8').split('\n')
        return [line for line in output if line.strip()]
    except:
        return []

def main():
    metrics = get_node_metrics() + get_vm_status()
    logs = get_logs()
    
    report = {
        "machine_name": MACHINE_NAME,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": metrics,
        "logs": logs
    }
    
    try:
        response = requests.post(COLLECTOR_URL, json=report, timeout=10)
        print(f"Report sent. Status: {response.status_code}")
    except Exception as e:
        print(f"Failed to send report: {e}")

if __name__ == "__main__":
    main()
