import os
import sys
import time
import yaml
import logging
import socket
import subprocess
import json
import httpx
import psutil
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# --- Logging Setup ---
LOG_DIR = "/var/log/wigo"
LOG_FILE = os.path.join(LOG_DIR, "agent.log")

if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except PermissionError:
        # Fallback for local testing
        LOG_FILE = "agent.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("wigo-agent")

# --- Configuration ---
CONFIG_PATH = "/etc/wigo/config.yaml"
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = "config.yaml"

with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

CERT_DIR = config['paths'].get('cert_dir', "/etc/wigo/certs")
AGENT_KEY_PATH = os.path.join(CERT_DIR, "agent.key")
AGENT_CERT_PATH = os.path.join(CERT_DIR, "agent.pem")
CA_CERT_PATH = os.path.join(CERT_DIR, "ca.pem")

class WigoAgent:
    def __init__(self):
        self.hostname = config['agent'].get('hostname', socket.gethostname())
        self.mgmt_url = config['controller']['management_url']
        self.api_url = config['controller']['agent_api_url']
        self.token = config['controller']['registration_token']
        self.poll_interval = config['agent'].get('poll_interval', 10)
        
        self.ssl_context = None

    def ensure_identity(self):
        """Generates key and CSR if cert doesn't exist."""
        if os.path.exists(AGENT_CERT_PATH) and os.path.exists(AGENT_KEY_PATH):
            logger.info("Certificate and key found.")
            return

        logger.info("Identity not found. Generating new key and CSR...")
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        with open(AGENT_KEY_PATH, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IL"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Center"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "WIGO"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "WIGO AI Agent"),
            x509.NameAttribute(NameOID.COMMON_NAME, self.hostname),
        ])).sign(key, hashes.SHA256(), default_backend())

        csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()
        self.register(csr_pem)

    def register(self, csr_pem):
        """Register with the controller using the token."""
        logger.info(f"Registering with controller at {self.mgmt_url}...")
        
        ip_addr = socket.gethostbyname(socket.gethostname())
        
        payload = {
            "hostname": self.hostname,
            "ip_address": ip_addr,
            "brand": "Ubuntu",
            "company": "Internal",
            "module": "local",
            "software_version": "1.0.0",
            "registration_token": self.token,
            "csr": csr_pem
        }
        
        try:
            with httpx.Client(verify=False) as client:
                resp = client.post(f"{self.mgmt_url}/api/register", json=payload, timeout=30)
                if resp.status_code != 200:
                    logger.error(f"Registration failed: {resp.text}")
                    sys.exit(1)
                
                data = resp.json()
                with open(AGENT_CERT_PATH, "w") as f:
                    f.write(data['certificate'])
                with open(CA_CERT_PATH, "w") as f:
                    f.write(data['ca_cert'])
                
                logger.info("Successfully registered and stored certificates.")
        except Exception as e:
            logger.error(f"Registration request failed: {str(e)}")
            sys.exit(1)

    def setup_mtls(self):
        """Configures SSL context for mTLS."""
        import ssl
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=CA_CERT_PATH)
        ctx.load_cert_chain(certfile=AGENT_CERT_PATH, keyfile=AGENT_KEY_PATH)
        # For development/self-signed, we might need to disable hostname check if using localhost
        if "localhost" in self.api_url or "127.0.0.1" in self.api_url:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_REQUIRED # Still require server cert
        
        self.ssl_context = ctx

    async def poll_actions(self):
        """Polls the Controller for pending actions."""
        async with httpx.AsyncClient(verify=self.ssl_context) as client:
            try:
                resp = await client.get(f"{self.api_url}/api/actions/pending?hostname={self.hostname}")
                if resp.status_code == 200:
                    commands = resp.json().get('commands', [])
                    for cmd in commands:
                        await self.execute_action(cmd)
                else:
                    logger.warning(f"Polling failed: {resp.status_code}")
            except Exception as e:
                logger.error(f"Error during polling: {str(e)}")

    async def execute_action(self, action):
        action_id = action['id']
        raw_command = action['command']
        
        logger.info(f"Executing action {action_id}: {raw_command}")
        
        # Action Schema Translation
        final_cmd = None
        if raw_command.startswith("RESTART"):
            parts = raw_command.split()
            service = parts[1] if len(parts) > 1 else None
            if service:
                final_cmd = f"sudo systemctl restart {service}"
        elif raw_command.startswith("CHECK_LOGS"):
            parts = raw_command.split()
            service = parts[parts.index("-u") + 1] if "-u" in parts else "wigo-agent"
            lines = parts[parts.index("-n") + 1] if "-n" in parts else "50"
            final_cmd = f"sudo journalctl -n {lines} -u {service}"
        elif raw_command == "GET_METRICS":
            await self.report_metrics(action_id)
            return
        else:
            # Fallback for raw commands proposed by AI
            final_cmd = raw_command

        if final_cmd:
            try:
                process = subprocess.Popen(
                    final_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate()
                exit_code = process.returncode
                await self.report_result(action_id, stdout, stderr, exit_code)
            except Exception as e:
                await self.report_result(action_id, "", str(e), 1)

    async def report_result(self, action_id, stdout, stderr, exit_code):
        async with httpx.AsyncClient(verify=self.ssl_context) as client:
            payload = {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code
            }
            try:
                await client.post(f"{self.api_url}/api/actions/{action_id}/result", json=payload)
                logger.info(f"Reported result for action {action_id}")
            except Exception as e:
                logger.error(f"Failed to report result: {str(e)}")

    async def report_metrics(self, action_id):
        # Gather metrics using psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        metrics = {
            "cpu_usage": f"{cpu}%",
            "memory_usage": f"{mem}%",
            "disk_usage": f"{disk}%",
            "load_avg": os.getloadavg()
        }
        await self.report_result(action_id, json.dumps(metrics, indent=2), "", 0)

    async def run(self):
        self.ensure_identity()
        self.setup_mtls()
        logger.info("Agent started and polling...")
        while True:
            await self.poll_actions()
            await asyncio.sleep(self.poll_interval)

if __name__ == "__main__":
    import asyncio
    agent = WigoAgent()
    asyncio.run(agent.run())
