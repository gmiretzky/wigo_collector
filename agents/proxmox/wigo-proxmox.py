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
import asyncio
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
logger = logging.getLogger("wigo-proxmox")

# --- Configuration ---
CONFIG_PATH = "/etc/wigo/config.yaml"
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = "config.yaml"

try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    sys.exit(1)

CERT_DIR = config['paths'].get('cert_dir', "/etc/wigo/certs")
AGENT_KEY_PATH = os.path.join(CERT_DIR, "agent.key")
AGENT_CERT_PATH = os.path.join(CERT_DIR, "agent.pem")
CA_CERT_PATH = os.path.join(CERT_DIR, "ca.pem")

class WigoProxmoxAgent:
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

        if not os.path.exists(CERT_DIR):
            os.makedirs(CERT_DIR, exist_ok=True)

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
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "WIGO Proxmox Agent"),
            x509.NameAttribute(NameOID.COMMON_NAME, self.hostname),
        ])).sign(key, hashes.SHA256(), default_backend())

        csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()
        self.register(csr_pem)

    def register(self, csr_pem):
        """Register with the controller using the token."""
        logger.info(f"Registering with controller at {self.mgmt_url}...")
        
        try:
            ip_addr = socket.gethostbyname(socket.gethostname())
        except:
            ip_addr = "127.0.0.1"
        
        payload = {
            "hostname": self.hostname,
            "ip_address": ip_addr,
            "brand": "Proxmox",
            "company": "Internal",
            "module": "proxmox",
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
        
        if "localhost" in self.api_url or "127.0.0.1" in self.api_url:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_REQUIRED
        
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

    async def get_proxmox_metrics(self):
        """Collects metrics from Proxmox CLI tools."""
        metrics = {
            "timestamp": time.time(),
            "host": {},
            "vms": [],
            "lxc": []
        }
        
        # Host Status
        try:
            res = subprocess.run(["pvesh", "get", "/nodes/localhost/status", "--output-format", "json"], capture_output=True, text=True)
            if res.returncode == 0:
                metrics['host'] = json.loads(res.stdout)
        except Exception as e:
            logger.error(f"Failed to get host status: {e}")

        # QEMU VMs
        try:
            res = subprocess.run(["pvesh", "get", "/nodes/localhost/qemu", "--output-format", "json"], capture_output=True, text=True)
            if res.returncode == 0:
                metrics['vms'] = json.loads(res.stdout)
        except Exception as e:
            logger.error(f"Failed to get VM list: {e}")

        # LXC Containers
        try:
            res = subprocess.run(["pvesh", "get", "/nodes/localhost/lxc", "--output-format", "json"], capture_output=True, text=True)
            if res.returncode == 0:
                metrics['lxc'] = json.loads(res.stdout)
        except Exception as e:
            logger.error(f"Failed to get LXC list: {e}")
            
        return metrics

    async def get_logs(self):
        """Collects critical logs from syslog and pveproxy."""
        logs = []
        try:
            # Get last 20 lines of syslog related to pve
            res = subprocess.run(["sudo", "journalctl", "-t", "pveproxy", "-t", "pvedaemon", "-t", "pve-cluster", "-n", "20", "--no-pager"], capture_output=True, text=True)
            if res.returncode == 0:
                logs.append({"source": "journalctl", "content": res.stdout})
            
            # Check for failed migrations or cluster errors in syslog specifically
            res = subprocess.run(["sudo", "grep", "-iE", "error|failed|migration", "/var/log/syslog", "|", "tail", "-n", "10"], shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                logs.append({"source": "syslog_grep", "content": res.stdout})
        except Exception as e:
            logger.error(f"Failed to collect logs: {e}")
            
        return logs

    async def execute_action(self, action):
        action_id = action['id']
        raw_command = action['command']
        
        logger.info(f"Executing action {action_id}: {raw_command}")
        
        if raw_command == "GET_METRICS":
            px_metrics = await self.get_proxmox_metrics()
            hw_metrics = {
                "cpu": psutil.cpu_percent(interval=1),
                "mem": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('/').percent
            }
            logs = await self.get_logs()
            
            combined = {
                "proxmox": px_metrics,
                "hardware": hw_metrics,
                "logs": logs
            }
            await self.report_result(action_id, json.dumps(combined, indent=2), "", 0)
            return

        # Proxmox Specific Commands: VM_START:100, VM_STOP:100, CT_RESTART:101, SNAPSHOT_CREATE:100:name
        parts = raw_command.split(':')
        cmd_type = parts[0]
        vmid = parts[1] if len(parts) > 1 else None
        
        if vmid and not vmid.isdigit():
            await self.report_result(action_id, "", f"Invalid VMID: {vmid}", 1)
            return

        final_cmd = None
        if cmd_type == "VM_START":
            final_cmd = f"sudo qm start {vmid}"
        elif cmd_type == "VM_STOP":
            final_cmd = f"sudo qm stop {vmid}"
        elif cmd_type == "CT_RESTART":
            final_cmd = f"sudo pct restart {vmid}"
        elif cmd_type == "SNAPSHOT_CREATE":
            snap_name = parts[2] if len(parts) > 2 else f"wigo_snap_{int(time.time())}"
            final_cmd = f"sudo qm snapshot {vmid} {snap_name}"
        else:
            # Fallback/Unknown
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

    async def run(self):
        self.ensure_identity()
        self.setup_mtls()
        logger.info("WIGO Proxmox Agent started and polling...")
        while True:
            await self.poll_actions()
            await asyncio.sleep(self.poll_interval)

if __name__ == "__main__":
    agent = WigoProxmoxAgent()
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user.")
