import uvicorn
import multiprocessing
import os
from src.wigo.pki import pki

def run_management():
    print("[*] Starting Management Interface on port 5000 (HTTP)")
    uvicorn.run("src.wigo.app_management:app", host="0.0.0.0", port=5000, reload=False)

def run_agents():
    print("[*] Starting Agent Interface on port 8443 (HTTPS mTLS)")
    pki.ensure_ca()
    
    # SSL Configuration
    ssl_keyfile = os.path.join("certs/ca", "rootCA.key")
    ssl_certfile = os.path.join("certs/ca", "rootCA.pem")
    ssl_ca_certs = os.path.join("certs/ca", "rootCA.pem")

    uvicorn.run(
        "src.wigo.app_agents:app", 
        host="0.0.0.0", 
        port=8443, 
        reload=False,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
        ssl_ca_certs=ssl_ca_certs,
        ssl_cert_reqs=2 # ssl.CERT_REQUIRED
    )

if __name__ == "__main__":
    # Create processes for both servers
    p1 = multiprocessing.Process(target=run_management)
    p2 = multiprocessing.Process(target=run_agents)

    p1.start()
    p2.start()

    p1.join()
    p2.join()
