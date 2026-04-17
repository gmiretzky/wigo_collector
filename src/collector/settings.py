import yaml
import os

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'config.yaml'))

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f) or {}

def save_config(config_data):
    # Ensure directory exists
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False)

def get_config_section(section, default=None):
    config = load_config()
    return config.get(section, default or {})
