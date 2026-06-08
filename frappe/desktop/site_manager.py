from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from frappe.desktop._utils import (
	apply_local_sqlite_config,
	bench_root,
	db_path_for,
	read_site_config,
	resolve_sites_path,
	site_path,
	sqlite_integrity_check,
	checkpoint_wal,
	copy_site_tree,
	write_json,
)


def _copy_sqlite_skeleton(destination: Path) -> None:
	source = bench_root() / "frappe" / "database" / "sqlite" / "framework_sqlite.db"
	if not source.exists():
		raise FileNotFoundError(f"SQLite framework skeleton missing: {source}")
	destination.parent.mkdir(parents=True, exist_ok=True)
	shutil.copy2(source, destination)
	conn = sqlite3.connect(str(destination))
	try:
		conn.execute("PRAGMA journal_mode = WAL")
	finally:
		conn.close()


def _installed_apps_from_config(config: dict[str, Any]) -> list[str]:
	apps = config.get("installed_apps") or config.get("apps") or []
	return sorted(apps) if isinstance(apps, list) else []


def list_sites(sites_path: str | Path | None = None) -> list[dict[str, Any]]:
	root = resolve_sites_path(sites_path)
	if not root.exists():
		return []
	sites: list[dict[str, Any]] = []
	for path in sorted(p for p in root.iterdir() if p.is_dir()):
		config = read_site_config(path.name, root)
		db_path = db_path_for(path.name, root)
		db_exists = db_path.exists()
		health = sqlite_integrity_check(db_path) if db_exists else "missing_db"
		sites.append(
			{
				"site_name": path.name,
				"site_path": str(path),
				"db_path": str(db_path),
				"installed_apps": _installed_apps_from_config(config),
				"db_exists": db_exists,
				"health": health,
			}
		)
	return sites


def create_site(site_name: str, apps: list[str] | None = None, force: bool = False, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	target = site_path(site_name, root)
	if target.exists():
		if not force:
			raise FileExistsError(f"Site already exists: {target}")
		shutil.rmtree(target)

	(target / "db").mkdir(parents=True, exist_ok=True)
	(target / "public" / "files").mkdir(parents=True, exist_ok=True)
	(target / "private" / "files").mkdir(parents=True, exist_ok=True)
	(target / "logs").mkdir(parents=True, exist_ok=True)
	config = apply_local_sqlite_config(site_name, root)
	_copy_sqlite_skeleton(db_path_for(site_name, root))
	if apps:
		config["installed_apps"] = sorted(set(apps))
		write_json(target / "site_config.json", config)
	return {"site_name": site_name, "site_path": str(target), "db_path": str(db_path_for(site_name, root)), "created": True}


def remove_site(site_name: str, force: bool = False, sites_path: str | Path | None = None) -> dict[str, Any]:
	target = site_path(site_name, sites_path)
	if not target.exists():
		return {"site_name": site_name, "removed": False, "reason": "missing"}
	if force:
		shutil.rmtree(target)
		return {"site_name": site_name, "removed": True, "mode": "deleted"}
	archive_root = target.parent / ".archived"
	archive_root.mkdir(parents=True, exist_ok=True)
	archived = archive_root / f"{site_name}.{int(time.time())}"
	shutil.move(str(target), str(archived))
	return {"site_name": site_name, "removed": True, "mode": "archived", "archive_path": str(archived)}


def clone_site(source_site: str, target_site: str, force: bool = False, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	source = site_path(source_site, root)
	if not source.exists():
		raise FileNotFoundError(f"Source site missing: {source}")
	checkpoint_wal(db_path_for(source_site, root))
	target = site_path(target_site, root)
	copy_site_tree(source, target, force=force)
	config = read_site_config(target_site, root)
	old_db_name = config.get("db_name") or source_site
	config["db_name"] = target_site
	write_json(target / "site_config.json", config)
	old_db = target / "db" / f"{old_db_name}.db"
	new_db = target / "db" / f"{target_site}.db"
	if old_db.exists() and old_db != new_db:
		old_db.rename(new_db)
	return {"source_site": source_site, "target_site": target_site, "site_path": str(target), "db_path": str(new_db)}


def export_site(site_name: str, output_path: str | Path, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	source = site_path(site_name, root)
	if not source.exists():
		raise FileNotFoundError(f"Site missing: {source}")
	checkpoint_wal(db_path_for(site_name, root))
	archive = Path(output_path).expanduser().resolve()
	archive.parent.mkdir(parents=True, exist_ok=True)
	manifest = {
		"format": "frappe-sqlite-site-v1",
		"site_name": site_name,
		"db_path": str(db_path_for(site_name, root).relative_to(source)),
		"created_at": int(time.time()),
	}
	manifest_path = source / "manifest.json"
	write_json(manifest_path, manifest)
	try:
		with tarfile.open(archive, "w:gz") as tar:
			tar.add(source, arcname=site_name)
	finally:
		manifest_path.unlink(missing_ok=True)
	return {"site_name": site_name, "archive": str(archive), "manifest": manifest}


def import_site(input_path: str | Path, site_name: str | None = None, force: bool = False, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	archive = Path(input_path).expanduser().resolve()
	if not archive.exists():
		raise FileNotFoundError(f"Archive missing: {archive}")
	root.mkdir(parents=True, exist_ok=True)
	with tempfile.TemporaryDirectory() as tmp:
		staging = Path(tmp)
		with tarfile.open(archive, "r:gz") as tar:
			members = tar.getmembers()
			top = members[0].name.split("/", 1)[0] if members else None
			if not top:
				raise ValueError("Archive has no site directory")
			tar.extractall(staging)
		target_name = site_name or top
		target = root / target_name
		if target.exists():
			if not force:
				raise FileExistsError(f"Target site already exists: {target}")
			shutil.rmtree(target)
		shutil.move(str(staging / top), str(target))
	config = read_site_config(target_name, root)
	old_db_name = config.get("db_name") or target_name
	config["db_name"] = target_name
	write_json(target / "site_config.json", config)
	old_db = target / "db" / f"{old_db_name}.db"
	new_db = target / "db" / f"{target_name}.db"
	if old_db.exists() and old_db != new_db:
		old_db.rename(new_db)
	health = sqlite_integrity_check(db_path_for(target_name, root))
	return {"site_name": target_name, "site_path": str(target), "health": health}


def _main() -> None:
	parser = argparse.ArgumentParser(description="Local SQLite site lifecycle helpers")
	sub = parser.add_subparsers(dest="command", required=True)
	sub.add_parser("list")
	create = sub.add_parser("create")
	create.add_argument("site")
	create.add_argument("--force", action="store_true")
	args = parser.parse_args()
	if args.command == "list":
		print(json.dumps(list_sites(), indent=2))
	elif args.command == "create":
		print(json.dumps(create_site(args.site, force=args.force), indent=2))


if __name__ == "__main__":
	_main()
