import yaml
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = os.getenv("WIGO_CONFIG_DIR", BASE_DIR / "config" / "commands")

def load_brand_configs():
    configs = {}
    if not os.path.exists(CONFIG_DIR):
        return configs
    
    for filename in os.listdir(CONFIG_DIR):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            brand = filename.rsplit(".", 1)[0].lower()
            with open(os.path.join(CONFIG_DIR, filename), "r") as f:
                configs[brand] = yaml.safe_load(f) or {}
    return configs

BRAND_CONFIGS = load_brand_configs()

def get_permission_level(brand: str, command: str) -> int:
    brand = (brand or "generic").lower()
    # Try brand-specific config, fallback to generic
    safe_commands = BRAND_CONFIGS.get(brand, BRAND_CONFIGS.get("generic", {}))
    
    # Check for exact matches or prefix matches
    # Longest match wins
    best_match_level = 2 # Default to Secure
    best_match_len = -1
    
    for safe_cmd, level in safe_commands.items():
        if command.startswith(safe_cmd):
            if len(safe_cmd) > best_match_len:
                best_match_len = len(safe_cmd)
                best_match_level = level
                
    return best_match_level
