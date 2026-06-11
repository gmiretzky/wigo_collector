import os
import sys
import time
import yaml
import logging
import socket
import subprocess
import json
import shlex
import httpx
import psutil
import asyncio
import uuid

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

import hmac
import hashlib

class WigoAgent:
    def __init__(self):
        self.hostname = config['agent'].get('hostname', socket.gethostname())
        self.mgmt_url = config['controller']['management_url']
        self.api_url = config['controller']['agent_api_url']
        self.token = config['controller']['registration_token']
        self.poll_interval = config['agent'].get('poll_interval', 10)
        
    def generate_hmac(self, parts):
        msg = "".join(str(p) for p in parts)
        return hmac.new(self.token.encode(), msg.encode(), hashlib.sha256).hexdigest()

    def collect_telemetry(self) -> str:
        cpu = psutil.cpu_percent(interval=1)
        load = os.getloadavg()
        mem = psutil.virtual_memory()
        disks = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append(f"{part.mountpoint}: {usage.percent}%")
            except PermissionError:
                pass
        top_procs = sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']), key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:5]
        procs_str = ", ".join(f"{p.info['name']}({p.info['cpu_percent']}%)" for p in top_procs)
        return (
            f"CPU: {cpu}% | Load: {load[0]:.2f},{load[1]:.2f},{load[2]:.2f} | "
            f"RAM: {mem.used // 1024 // 1024}MB/{mem.total // 1024 // 1024}MB ({mem.percent}%) | "
            f"Disk: {'; '.join(disks)} | "
            f"Top procs: {procs_str}"
        )

    def register(self):
        """Register with the controller using HMAC and token."""
        logger.info(f"Registering with controller at {self.mgmt_url}...")

        ip_addr = socket.gethostbyname(socket.gethostname())
        timestamp = int(time.time())
        nonce = str(uuid.uuid4())
        signature = self.generate_hmac([self.hostname, ip_addr, timestamp, nonce])

        payload = {
            "hostname": self.hostname,
            "ip_address": ip_addr,
            "brand": "Ubuntu",
            "company": "Internal",
            "module": "local",
            "software_version": "1.0.0",
            "registration_token": self.token,
            "timestamp": timestamp,
            "nonce": nonce,
            "hmac_signature": signature
        }
        
        try:
            with httpx.Client(verify=True) as client:
                resp = client.post(f"{self.mgmt_url}/api/register", json=payload, timeout=30)
                if resp.status_code != 200:
                    logger.error(f"Registration failed: {resp.text}")
                    sys.exit(1)
                
                logger.info("Successfully registered via HMAC authentication.")
        except Exception as e:
            logger.error(f"Registration request failed: {str(e)}")
            sys.exit(1)

    async def send_telemetry(self):
        data = self.collect_telemetry()
        timestamp = int(time.time())
        nonce = str(uuid.uuid4())
        signature = self.generate_hmac([self.hostname, timestamp, nonce])
        payload = {
            "hostname": self.hostname,
            "data": data,
            "timestamp": timestamp,
            "nonce": nonce,
            "hmac_signature": signature
        }
        async with httpx.AsyncClient(verify=True) as client:
            try:
                await client.post(f"{self.api_url}/api/actions/telemetry", json=payload, timeout=15)
            except Exception as e:
                logger.error(f"Failed to send telemetry: {str(e)}")

    async def poll_actions(self):
        """Polls the Controller for pending actions."""
        timestamp = int(time.time())
        nonce = str(uuid.uuid4())
        signature = self.generate_hmac([self.hostname, timestamp, nonce])

        params = {
            "hostname": self.hostname,
            "timestamp": timestamp,
            "nonce": nonce,
            "hmac_signature": signature
        }

        async with httpx.AsyncClient(verify=True) as client:
            try:
                resp = await client.get(f"{self.api_url}/api/actions/pending", params=params)
                if resp.status_code == 200:
                    commands = resp.json().get('commands', [])
                    for cmd in commands:
                        await self.execute_action(cmd)
                else:
                    logger.warning(f"Polling failed: {resp.status_code}")
            except Exception as e:
                logger.error(f"Error during polling: {str(e)})")

    async def execute_action(self, cmd: dict):
        action_id = cmd['id']
        command = cmd['command']
        trace_id = cmd.get('trace_id')
        logger.info(f"[{trace_id}] Executing action {action_id}: {command}")

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *shlex.split(command),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=30)
            exit_code = proc.returncode
        except asyncio.TimeoutError:
            if proc:
                proc.kill()
            stdout_b, stderr_b, exit_code = b"", b"Command timed out after 30 seconds", 1
        except Exception as e:
            stdout_b, stderr_b, exit_code = b"", str(e).encode(), 1

        await self.report_result(action_id, stdout_b.decode(), stderr_b.decode(), exit_code)

    async def report_result(self, action_id, stdout, stderr, exit_code):
        timestamp = int(time.time())
        nonce = str(uuid.uuid4())
        signature = self.generate_hmac([action_id, timestamp, nonce])

        payload = {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "timestamp": timestamp,
            "nonce": nonce,
            "hmac_signature": signature
        }
        async with httpx.AsyncClient(verify=True) as client:
            try:
                await client.post(f"{self.api_url}/api/actions/{action_id}/result", json=payload)
                logger.info(f"Reported result for action {action_id}")
            except Exception as e:
                logger.error(f"Failed to report result: {str(e)}")

    async def run(self):
        self.register()
        logger.info("Agent started and polling...")
        while True:
            await self.send_telemetry()
            await self.poll_actions()
            await asyncio.sleep(self.poll_interval)

if __name__ == "__main__":
    agent = WigoAgent()
    asyncio.run(agent.run())
