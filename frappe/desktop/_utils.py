from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from frappe.desktop import LOCAL_SQLITE_CONFIG


DEFAULT_PRODUCT_NAME = "FrappeSQLite"


@dataclass(frozen=True)
class CommandResult:
	command: list[str]
	returncode: int
	stdout: str
	stderr: str


def bench_root() -> Path:
	return Path(__file__).resolve().parents[2]


def default_sites_path() -> Path:
	for key in ("FRAPPE_SITES_PATH", "SITES_PATH"):
		if os.environ.get(key):
			return Path(os.environ[key]).expanduser().resolve()
	if os.environ.get("FRAPPE_SQLITE_DATA_DIR"):
		return Path(os.environ["FRAPPE_SQLITE_DATA_DIR"]).expanduser().resolve() / "sites"
	return Path.home() / "Library" / "Application Support" / DEFAULT_PRODUCT_NAME / "sites"


def resolve_sites_path(sites_path: str | os.PathLike[str] | None = None) -> Path:
	return Path(sites_path).expanduser().resolve() if sites_path else default_sites_path()


def site_path(site_name: str, sites_path: str | os.PathLike[str] | None = None) -> Path:
	return resolve_sites_path(sites_path) / site_name


def read_json(path: Path, default: Any = None) -> Any:
	if not path.exists():
		return default
	with path.open() as f:
		return json.load(f)


def write_json(path: Path, data: Any) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w") as f:
		json.dump(data, f, indent=2, sort_keys=True)
		f.write("\n")


def site_config_path(site_name: str, sites_path: str | os.PathLike[str] | None = None) -> Path:
	return site_path(site_name, sites_path) / "site_config.json"


def read_site_config(site_name: str, sites_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
	return read_json(site_config_path(site_name, sites_path), {}) or {}


def write_site_config(site_name: str, config: dict[str, Any], sites_path: str | os.PathLike[str] | None = None) -> None:
	write_json(site_config_path(site_name, sites_path), config)


def apply_local_sqlite_config(site_name: str, sites_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
	config = read_site_config(site_name, sites_path)
	config.update(LOCAL_SQLITE_CONFIG)
	config.setdefault("db_name", site_name)
	write_site_config(site_name, config, sites_path)
	return config


def db_path_for(site_name: str, sites_path: str | os.PathLike[str] | None = None) -> Path:
	config = read_site_config(site_name, sites_path)
	db_name = config.get("db_name") or site_name
	return site_path(site_name, sites_path) / "db" / f"{db_name}.db"


def checkpoint_wal(db_path: Path) -> None:
	if not db_path.exists():
		return
	conn = sqlite3.connect(str(db_path))
	try:
		conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
	finally:
		conn.close()


def sqlite_integrity_check(db_path: Path) -> str:
	if not db_path.exists():
		return "missing"
	conn = sqlite3.connect(str(db_path))
	try:
		row = conn.execute("PRAGMA integrity_check").fetchone()
		return row[0] if row else "unknown"
	finally:
		conn.close()


def copy_site_tree(source: Path, target: Path, *, force: bool = False) -> None:
	if target.exists():
		if not force:
			raise FileExistsError(f"Target site already exists: {target}")
		shutil.rmtree(target)
	shutil.copytree(source, target, symlinks=True)


def run_command(command: list[str], *, cwd: Path | None = None, check: bool = True) -> CommandResult:
	proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
	result = CommandResult(command=command, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
	if check and proc.returncode:
		raise RuntimeError(
			f"Command failed ({proc.returncode}): {' '.join(command)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
		)
	return result

