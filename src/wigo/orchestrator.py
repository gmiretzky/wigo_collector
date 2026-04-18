import docker
import os
from typing import Dict

class Orchestrator:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            print(f"[-] Docker not available: {e}")
            self.client = None

    def spin_up_proxy(self, agent_id: int, brand: str, metadata: Dict):
        """
        Spin up a specialized Docker container for remote polling.
        """
        if not self.client:
            return None
        
        image_map = {
            "mikrotik": "wigo-proxy-mikrotik:latest",
            "cisco": "wigo-proxy-cisco:latest"
        }
        
        image = image_map.get(brand.lower())
        if not image:
            print(f"[-] No proxy image for brand: {brand}")
            return None

        container_name = f"wigo-agent-{agent_id}"
        
        try:
            # Check if already running
            self.client.containers.get(container_name).stop()
            self.client.containers.get(container_name).remove()
        except:
            pass

        try:
            container = self.client.containers.run(
                image,
                name=container_name,
                detach=True,
                environment={
                    "CONTROLLER_URL": os.getenv("CONTROLLER_URL", "http://wigo-controller:8443"),
                    "AGENT_ID": agent_id,
                    "TARGET_IP": metadata.get("ip_address"),
                    "SSH_USER": metadata.get("ssh_user"),
                    # Secrets should ideally be handled via Docker Secrets or a Vault
                    "SSH_KEY": metadata.get("ssh_key") 
                },
                restart_policy={"Name": "always"}
            )
            return container.id
        except Exception as e:
            print(f"[-] Failed to spin up proxy: {e}")
            return None

orchestrator = Orchestrator()
