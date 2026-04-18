import requests
import os
import socket
import datetime
import time
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

REGISTRATION_URL = "http://localhost:5000/api"
AGENT_API_URL = "https://localhost:8443/api"
CERT_FILE = "agent.pem"
KEY_FILE = "agent.key"
CA_FILE = "rootCA.pem"

def generate_csr(hostname):
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    with open(KEY_FILE, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "WIGO Agent"),
    ])).sign(key, hashes.SHA256(), default_backend())

    return csr.public_bytes(serialization.Encoding.PEM).decode()

def register():
    hostname = socket.gethostname()
    print(f"[*] Registering agent: {hostname}")
    csr = generate_csr(hostname)
    
    payload = {
        "hostname": hostname,
        "ip_address": socket.gethostbyname(hostname),
        "brand": "Ubuntu",
        "company": "HomeLab",
        "module": "local",
        "software_version": "2.0.0",
        "csr": csr
    }
    
    try:
        response = requests.post(f"{REGISTRATION_URL}/register", json=payload)
        response.raise_for_status()
        data = response.json()
        
        with open(CERT_FILE, "w") as f:
            f.write(data["certificate"])
        with open(CA_FILE, "w") as f:
            f.write(data["ca_cert"])
            
        print("[+] Registration successful. Certificates saved.")
    except Exception as e:
        print(f"[-] Registration failed: {e}")
        exit(1)

def send_telemetry():
    hostname = socket.gethostname()
    # Mock telemetry
    telemetry = f"CPU Load: 15%\nMemory: 2GB/8GB\nDisk: 50% used\nTimestamp: {datetime.datetime.now()}"
    
    payload = {
        "hostname": hostname,
        "data": telemetry
    }
    
    # In real deploy, use certs=(CERT_FILE, KEY_FILE) and verify=CA_FILE
    try:
        response = requests.post(
            f"{AGENT_API_URL}/actions/telemetry", 
            json=payload,
            cert=(CERT_FILE, KEY_FILE),
            verify=CA_FILE
        )
        response.raise_for_status()
        print(f"[+] Telemetry sent: {response.json()}")
    except Exception as e:
        print(f"[-] Failed to send telemetry: {e}")

def check_for_actions():
    hostname = socket.gethostname()
    try:
        response = requests.get(
            f"{AGENT_API_URL}/actions/pending", 
            params={"hostname": hostname},
            cert=(CERT_FILE, KEY_FILE),
            verify=CA_FILE
        )
        response.raise_for_status()
        commands = response.json().get("commands", [])
        for cmd in commands:
            print(f"[*] EXECUTING COMMAND: {cmd['command']}")
            # In real agent: os.system(cmd['command'])
    except Exception as e:
        print(f"[-] Failed to check actions: {e}")

if __name__ == "__main__":
    if not os.path.exists(CERT_FILE):
        register()
    
    while True:
        send_telemetry()
        check_for_actions()
        print("[*] Sleeping for 60 seconds...")
        time.sleep(60) # Test frequently, in production use 15m (900s)
