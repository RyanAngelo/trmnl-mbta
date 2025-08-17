import fcntl
import json
import logging
import os

from src.mbta.constants import CONFIG_FILE
from src.mbta.models import RouteConfig

logger = logging.getLogger(__name__)

def safe_save_config(config: RouteConfig):
    """Save configuration to file with proper locking."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            # Get an exclusive lock
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(config.model_dump(), f, indent=2)
            finally:
                # Release the lock
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except IOError as e:
        logger.error(f"Error saving config: {str(e)}")
        raise RuntimeError(f"Could not save configuration: {str(e)}")

def safe_load_config() -> RouteConfig:
    """Load configuration from file with proper error handling."""
    try:
        if not os.path.exists(CONFIG_FILE):
            default_config = RouteConfig(route_id="Red")
            safe_save_config(default_config)
            return default_config

        with open(CONFIG_FILE, "r") as f:
            # Get a shared lock for reading
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                config_data = json.load(f)
            finally:
                # Release the lock
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return RouteConfig(**config_data)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Error loading config: {str(e)}")
        raise RuntimeError(f"Could not load configuration: {str(e)}") 
