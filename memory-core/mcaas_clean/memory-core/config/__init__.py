"""
config/__init__.py — Configuration loader for Atlas.
Reads atlas.yaml, expands environment variables, returns merged dict.
"""
from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Any

_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-(.*?))?\}")


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        def replacer(m):
            var, default = m.group(1), m.group(2) or ""
            return os.environ.get(var, default)
        return _ENV_PATTERN.sub(replacer, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def load_config(path: str = None) -> dict:
    import yaml
    config_path = Path(path or os.environ.get("ATLAS_CONFIG", "config/atlas.yaml"))
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / "config" / "atlas.yaml"

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return _expand(raw or {})
