"""Configuration loader / saver with deep-merge and validation."""
from __future__ import annotations

import json
import os
import copy
from typing import Any, Dict

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.default.json')
USER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'config.json')


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override into base. override wins."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_defaults() -> Dict[str, Any]:
    with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_config(path: str = USER_CONFIG_PATH) -> Dict[str, Any]:
    """Load user config, falling back to defaults for missing keys."""
    defaults = load_defaults()
    if not os.path.exists(path):
        return copy.deepcopy(defaults)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            user = json.load(f)
    except (json.JSONDecodeError, OSError):
        return copy.deepcopy(defaults)
    return deep_merge(defaults, user)


def save_config(config: Dict[str, Any], path: str = USER_CONFIG_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
