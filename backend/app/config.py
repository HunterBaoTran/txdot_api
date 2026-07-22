from __future__ import annotations

import os
from pathlib import Path

import yaml

from .contracts import AppConfig


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path or os.getenv("VERATEX_CONFIG", "config/demo.yaml"))
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    with config_path.open(encoding="utf-8") as handle:
        return AppConfig.model_validate(yaml.safe_load(handle))
