import os
import time
import hmac
import hashlib
import uuid
import tempfile
import requests
from netmiko import ConnectHandler

CONTROLLER_URL = os.getenv("CONTROLLER_URL")
TARGET_IP = os.getenv("TARGET_IP")
SSH_USER = os.getenv("SSH_USER")
SSH_KEY = os.getenv("SSH_KEY")
REGISTRATION_TOKEN = os.getenv("REGISTRATION_TOKEN")
HOSTNAME = os.getenv("HOSTNAME", f"mikrotik-{TARGET_IP}")


def generate_hmac(token: str, parts: list) -> str:
    msg = "".join(str(p) for p in parts)
    return hmac.new(token.encode(), msg.encode(), hashlib.sha256).hexdigest()


def collect_mikrotik_data(key_path: str) -> str:
    device = {
        'device_type': 'mikrotik_routeros',
        'host': TARGET_IP,
        'username': SSH_USER,
        'use_keys': True,
        'key_file': key_path,
    }
    try:
        with ConnectHandler(**device) as net_connect:
            cpu = net_connect.send_command("/system resource print")
            logs = net_connect.send_command("/log print count=20")
            return f"RESOURCES:\n{cpu}\n\nLOGS:\n{logs}"
    except Exception as e:
        return f"ERROR COLLECTING DATA: {e}"


def main():
    print(f"[*] Starting MikroTik Proxy for {TARGET_IP}")

    key_path = None
    if SSH_KEY:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.key') as f:
            f.write(SSH_KEY)
            key_path = f.name
        os.chmod(key_path, 0o600)

    try:
        while True:
            data = collect_mikrotik_data(key_path) if key_path else "ERROR: No SSH key configured"

            timestamp = int(time.time())
            nonce = str(uuid.uuid4())
            signature = generate_hmac(REGISTRATION_TOKEN, [HOSTNAME, timestamp, nonce])

            payload = {
                "hostname": HOSTNAME,
                "data": data,
                "timestamp": timestamp,
                "nonce": nonce,
                "hmac_signature": signature,
            }
            try:
                requests.post(f"{CONTROLLER_URL}/api/actions/telemetry", json=payload, timeout=15)
            except Exception as e:
                print(f"[!] Failed to post telemetry: {e}")

            time.sleep(900)  # 15 minutes
    finally:
        if key_path and os.path.exists(key_path):
            os.unlink(key_path)


if __name__ == "__main__":
    main()
