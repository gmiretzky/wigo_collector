import os
import time
import requests
from netmiko import ConnectHandler

CONTROLLER_URL = os.getenv("CONTROLLER_URL")
TARGET_IP = os.getenv("TARGET_IP")
SSH_USER = os.getenv("SSH_USER")
SSH_KEY = os.getenv("SSH_KEY") # This would be a path or content

def collect_mikrotik_data():
    device = {
        'device_type': 'mikrotik_routeros',
        'host': TARGET_IP,
        'username': SSH_USER,
        'use_keys': True,
        'key_file': '/app/ssh_key' # Mounted or written from env
    }
    
    # Write key to file if provided via env
    if SSH_KEY and not os.path.exists('/app/ssh_key'):
        with open('/app/ssh_key', 'w') as f:
            f.write(SSH_KEY)
        os.chmod('/app/ssh_key', 0o600)

    try:
        with ConnectHandler(**device) as net_connect:
            cpu = net_connect.send_command("/system resource print")
            logs = net_connect.send_command("/log print count=20")
            return f"RESOURCES:\n{cpu}\n\nLOGS:\n{logs}"
    except Exception as e:
        return f"ERROR COLLECTING DATA: {e}"

def main():
    print(f"[*] Starting MikroTik Proxy for {TARGET_IP}")
    while True:
        data = collect_mikrotik_data()
        payload = {
            "hostname": f"mikrotik-{TARGET_IP}",
            "data": data
        }
        try:
            requests.post(f"{CONTROLLER_URL}/api/actions/telemetry", json=payload)
        except:
            pass
        
        time.sleep(900) # 15 minutes

if __name__ == "__main__":
    main()
