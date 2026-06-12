"""Configuration management for CodeDNA."""
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "daemon": {"host": "127.0.0.1", "port": 7842, "workers": 2, "log_level": "INFO"},
    "logs": {"max_mb": 50, "retain_days": 7},
    "scan_history": {"retain_days": 90},
    "jobs": {"retain_days": 30},
    "harvester": {"max_file_bytes": 1048576, "store_bodies": False, "batch_size": 500},
    "features": {"rust_scanner": True, "ide_inline_hints": True, "evolution_report": False, "multi_language": False, "export": False},
    "rate_limit": {"requests_per_minute": 100},
}

def get_config_dir() -> Path:
    home = Path.home()
    config_dir = home / ".codedna"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_log_dir() -> Path:
    log_dir = get_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

def get_daemon_log_path() -> Path:
    return get_log_dir() / "daemon.log"

def load_config_file() -> dict:
    config_path = get_config_dir() / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse config file: {e}")
    return {}

def save_config_file(config: dict) -> None:
    with open(get_config_dir() / "config.json", "w") as f:
        json.dump(config, f, indent=2)

def get_config_value(key: str, default: Any = None) -> Any:
    config = load_config_file()
    keys = key.split(".")
    value = config
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    return value

def set_config_value(key: str, value: Any) -> None:
    config = load_config_file()
    keys = key.split(".")
    current = config
    for i, k in enumerate(keys[:-1]):
        if k not in current:
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value
    save_config_file(config)

def get_daemon_config() -> dict:
    config = load_config_file()
    daemon_config = config.get("daemon", {})
    result = DEFAULT_CONFIG["daemon"].copy()
    result.update(daemon_config)
    return result

def get_feature_flag(name: str) -> bool:
    return get_config_value(f"features.{name}", DEFAULT_CONFIG["features"].get(name, False))

def setup_logging(log_level: str = None) -> None:
    if log_level is None:
        log_level = get_daemon_config().get("log_level", "INFO")
    log_level = log_level.upper()
    import logging.config
    logging_config = {
        "version": 1, "disable_existing_loggers": False,
        "formatters": {"simple": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"}},
        "handlers": {"file": {"class": "logging.handlers.RotatingFileHandler", "filename": str(get_daemon_log_path()), "maxBytes": 10485760, "backupCount": 5, "formatter": "simple"},
                     "console": {"class": "logging.StreamHandler", "formatter": "simple"}},
        "root": {"level": log_level, "handlers": ["file", "console"]},
        "loggers": {"codedna": {"level": log_level, "handlers": ["file", "console"], "propagate": False}},
    }
    logging.config.dictConfig(logging_config)
