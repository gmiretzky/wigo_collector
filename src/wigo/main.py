import uvicorn
import multiprocessing
import os
import time
from src.wigo.pki import pki, CA_DIR

def run_management():
    print("[*] Starting Management Interface on port 5000 (HTTP)")
    uvicorn.run("src.wigo.app_management:app", host="0.0.0.0", port=5000, reload=False)

def run_agents():
    print("[*] Starting Agent Interface on port 8443 (HTTPS)")
    
    # SSL Configuration - Allow overrides via environment variables
    ssl_keyfile = os.getenv("WIGO_SERVER_KEY", os.path.join(CA_DIR, "rootCA.key"))
    ssl_certfile = os.getenv("WIGO_SERVER_CERT", os.path.join(CA_DIR, "rootCA.pem"))

    try:
        uvicorn.run(
            "src.wigo.app_agents:app", 
            host="0.0.0.0", 
            port=8443, 
            reload=False,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            ssl_cert_reqs=0 # ssl.CERT_NONE - No client certificates required
        )
    except Exception as e:
        print(f"[!] Agent Interface Error: {e}")

def monitor_certs(p_agents):
    """Monitor certificate files and restart agent process if they change."""
    last_mtime = 0
    cert_path = os.path.join(CA_DIR, "rootCA.pem")
    
    while True:
        try:
            if os.path.exists(cert_path):
                current_mtime = os.path.getmtime(cert_path)
                if last_mtime != 0 and current_mtime > last_mtime:
                    print("[*] Certificates changed! Restarting Agent Interface...")
                    p_agents.terminate()
                    p_agents.join()
                    
                    # Restart process
                    new_p = multiprocessing.Process(target=run_agents)
                    new_p.start()
                    p_agents = new_p
                last_mtime = current_mtime
        except Exception as e:
            print(f"[!] Monitor Error: {e}")
        time.sleep(5)

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs(CA_DIR, exist_ok=True)
    
    # Create processes for both servers
    p1 = multiprocessing.Process(target=run_management)
    p2 = multiprocessing.Process(target=run_agents)

    p1.start()
    p2.start()

    # Start monitor in main process
    monitor_certs(p2)

    p1.join()
