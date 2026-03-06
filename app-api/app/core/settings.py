from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    export_dir: str = "exports"
    default_query_days: int = 30
    cache_ttl_orgs_seconds: int = 600
    cache_ttl_groups_seconds: int = 600
    cache_ttl_total_seconds: int = 300


@dataclass
class DbConfig:
    enabled: bool = False
    db_type: str = "mysql"
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = ""
    view_name: str = ""


def _resolve_root_dir() -> Path:
    env_root = os.getenv("BODA_ROOT_DIR", "").strip()
    if env_root:
        env_path = Path(env_root).resolve()
        if (env_path / "config").exists():
            return env_path

    code_root = Path(__file__).resolve().parents[3]
    if (code_root / "config").exists():
        return code_root

    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        frozen_path = Path(frozen_base).resolve()
        if (frozen_path / "config").exists():
            return frozen_path

    exe_dir = Path(sys.executable).resolve().parent
    for candidate in [exe_dir, exe_dir.parent, Path.cwd().resolve()]:
        if (candidate / "config").exists():
            return candidate

    return code_root


ROOT_DIR = _resolve_root_dir()
CONFIG_DIR = ROOT_DIR / "config"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    return loaded or {}


def load_app_config() -> AppConfig:
    data = _read_yaml(CONFIG_DIR / "app.yaml")
    return AppConfig(
        host=data.get("host", "127.0.0.1"),
        port=int(data.get("port", 8000)),
        export_dir=data.get("export_dir", "exports"),
        default_query_days=int(data.get("default_query_days", 30)),
        cache_ttl_orgs_seconds=int(data.get("cache_ttl_orgs_seconds", 600)),
        cache_ttl_groups_seconds=int(data.get("cache_ttl_groups_seconds", 600)),
        cache_ttl_total_seconds=int(data.get("cache_ttl_total_seconds", 300)),
    )


def load_db_config() -> DbConfig:
    data = _read_yaml(CONFIG_DIR / "db.yaml")
    db_type = str(data.get("db_type", "")).strip().lower()
    if not db_type:
        try:
            port = int(data.get("port", 3306))
        except Exception:
            port = 3306
        db_type = "sqlserver" if port == 1433 else "mysql"

    return DbConfig(
        enabled=bool(data.get("enabled", False)),
        db_type=db_type,
        host=data.get("host", "127.0.0.1"),
        port=int(data.get("port", 3306)),
        user=data.get("user", "root"),
        password=data.get("password", ""),
        database=data.get("database", ""),
        view_name=data.get("view_name", ""),
    )


def load_export_columns() -> list[dict[str, str]]:
    data = _read_yaml(CONFIG_DIR / "export_columns.yaml")
    columns = data.get("columns", [])
    valid_columns: list[dict[str, str]] = []
    for column in columns:
        field = column.get("field")
        title = column.get("title")
        if field and title:
            valid_columns.append({"field": field, "title": title})
    return valid_columns


def load_view_mapping() -> dict[str, Any]:
    return _read_yaml(CONFIG_DIR / "view_mapping.yaml")


def load_dict_mapping() -> dict[str, dict[str, str]]:
    data = _read_yaml(CONFIG_DIR / "dict_mapping.yaml")
    result: dict[str, dict[str, str]] = {}
    for key, mapping in (data.get("dicts", {}) or {}).items():
        if isinstance(mapping, dict):
            result[key] = {str(k): str(v) for k, v in mapping.items()}
    return result
