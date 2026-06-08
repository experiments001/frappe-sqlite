from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from frappe.desktop._utils import bench_root, checkpoint_wal, db_path_for, run_command


def _script(name: str) -> Path:
	return bench_root() / "desktop" / "scripts" / name


def build_desktop_app(
	site_name: str | None = None,
	apps: list[str] | None = None,
	output_path: str | Path | None = None,
	product_name: str | None = None,
) -> dict[str, Any]:
	if site_name:
		checkpoint_wal(db_path_for(site_name))
	commands = []
	for script in ("build-sidecar.sh", "build-app.sh"):
		path = _script(script)
		if not path.exists():
			raise FileNotFoundError(f"Missing desktop build script: {path}")
		result = run_command([str(path)], cwd=bench_root())
		commands.append({"script": script, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]})
	return {
		"built": True,
		"commands": commands,
		"output_path": str(output_path) if output_path else str(bench_root() / "desktop" / "shell" / "src-tauri" / "target"),
		"product_name": product_name,
		"apps": apps or [],
	}


def rebuild_desktop_app() -> dict[str, Any]:
	return build_desktop_app()


def check_rebuild_needed() -> dict[str, Any]:
	root = bench_root()
	app = root / "desktop" / "shell" / "src-tauri" / "target" / "release" / "bundle" / "macos" / "frappe-sqlite-desktop.app"
	sidecar = root / "desktop" / "shell" / "src-tauri" / "binaries" / "frappe-sqlite-aarch64-apple-darwin"
	missing = [str(path) for path in (app, sidecar) if not path.exists()]
	return {"rebuild_needed": bool(missing), "missing": missing}


def _main() -> None:
	parser = argparse.ArgumentParser(description="Local SQLite desktop build helpers")
	parser.add_argument("--check", action="store_true")
	args = parser.parse_args()
	if args.check:
		print(json.dumps(check_rebuild_needed(), indent=2))
	else:
		print(json.dumps(build_desktop_app(), indent=2))


if __name__ == "__main__":
	_main()

