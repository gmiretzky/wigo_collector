import requests
from src.collector.settings import load_config

def send_notification(message: str, severity: str):
    config = load_config()
    webhooks = config.get("webhooks", {})
    
    # Pushover
    pushover = webhooks.get("pushover", {})
    if pushover.get("enabled"):
        try:
            requests.post(pushover["url"], data={
                "token": pushover["token"],
                "user": pushover["user"],
                "message": f"[{severity.upper()}] WIGO: {message}"
            }, timeout=5)
        except Exception as e:
            print(f"Failed to send Pushover notification: {e}")

    # Home Assistant
    ha = webhooks.get("homeassistant", {})
    if ha.get("enabled"):
        try:
            headers = {"Authorization": f"Bearer {ha['token']}", "Content-Type": "application/json"}
            requests.post(ha["url"], headers=headers, json={"state": message, "attributes": {"severity": severity}}, timeout=5)
        except Exception as e:
            print(f"Failed to send HA notification: {e}")

def forward_analysis(payload: dict):
    config = load_config()
    url = config.get("ai", {}).get("analysis_forwarding_webhook_url")
    if url:
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Failed to forward analysis: {e}")
