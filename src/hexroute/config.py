"""Configuration loader for hexroute."""

import os
from pathlib import Path
import tomllib
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Minimal fallback .env parser if python-dotenv is not yet initialized
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    if _k.strip() not in os.environ:
                        os.environ[_k.strip()] = _v.strip()


def find_config_file(custom_path: str | Path | None = None) -> Path | None:
    """Find config.toml in current directory, project root, or custom path."""
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            return p

    candidates = [
        Path.cwd() / "config.toml",
        Path(__file__).resolve().parent.parent.parent / "config.toml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def load_config(custom_path: str | Path | None = None) -> dict[str, Any]:
    """Load configuration from config.toml with sensible defaults."""
    defaults: dict[str, Any] = {
        "general": {
            "h3_resolution": 8,
            "home_lat": 51.5074,
            "home_lng": -0.1278,
            "default_budget_km": 10.0,
        },
        "scoring": {
            "enemy": 3.0,
            "unclaimed": 2.0,
            "ours": 0.0,
            "adjacent_bonus": 0.5,
        },
        "paths": {
            "data_dir": "data",
            "out_dir": "out",
            "cache_dir": "cache",
        },
    }

    config_path = find_config_file(custom_path)
    if config_path:
        with open(config_path, "rb") as f:
            user_config = tomllib.load(f)

        for section, values in user_config.items():
            if isinstance(values, dict) and section in defaults:
                defaults[section].update(values)
            else:
                defaults[section] = values

    return defaults
