"""Configuration loader for application settings and environment variables."""

import os
from pathlib import Path


def load_config(config_path=None):
    """Load configuration from YAML file or environment defaults.
    
    Args:
        config_path: Optional path to custom config file
        
    Returns:
        dict with merged configuration values
    """
    if config_path is None:
        config_path = os.environ.get("APP_CONFIG", "config.yaml")
    
    path = Path(config_path)
    if not path.exists():
        return get_default_config()
    
    with open(path, "r") as f:
        user_config = f.read() or {}
    
    defaults = get_default_config()
    merged = {**defaults, **user_config}
    return merged


def get_default_config():
    """Return default configuration values for the application."""
    return {
        "database": {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": int(os.environ.get("DB_PORT", 5432)),
            "name": os.environ.get("DB_NAME", "app_db")
        },
        "logging": {
            "level": os.environ.get("LOG_LEVEL", "INFO"),
            "format": "%(asctime)s [%(levelname)s] %(message)s"
        },
        "features": {
            "enable_cache": True,
            "max_connections": 100
        }
    }


def validate_config(config):
    """Validate that required configuration keys are present.
    
    Raises:
        ValueError if mandatory settings are missing or invalid
    """
    required_keys = ["database", "logging"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config section: {key}")


if __name__ == "__main__":
    cfg = load_config()
    validate_config(cfg)
    print("Configuration loaded successfully")
