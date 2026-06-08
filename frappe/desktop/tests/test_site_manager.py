from __future__ import annotations

import sqlite3
from pathlib import Path

from frappe.desktop.app_manager import resolve_app_source
from frappe.desktop.site_manager import clone_site, create_site, drop_site, export_site, import_site, list_sites, remove_site


def _make_db(path: Path) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	conn = sqlite3.connect(path)
	try:
		conn.execute("create table sample (name text primary key)")
		conn.execute("insert into sample values ('row-1')")
		conn.commit()
	finally:
		conn.close()


def test_site_lifecycle_roundtrip(tmp_path: Path) -> None:
	sites = tmp_path / "sites"
	created = create_site("alpha.localhost", apps=["frappe"], sites_path=sites)
	assert created["created"] is True
	_make_db(Path(created["db_path"]))

	listed = list_sites(sites)
	assert listed[0]["site_name"] == "alpha.localhost"
	assert listed[0]["db_exists"] is True
	assert listed[0]["health"] == "ok"

	cloned = clone_site("alpha.localhost", "beta.localhost", sites_path=sites)
	assert Path(cloned["db_path"]).exists()
	assert list_sites(sites)[1]["site_name"] == "beta.localhost"

	archive = tmp_path / "alpha.tar.gz"
	exported = export_site("alpha.localhost", archive, sites_path=sites)
	assert Path(exported["archive"]).exists()

	remove_site("alpha.localhost", force=True, sites_path=sites)
	assert "alpha.localhost" not in {site["site_name"] for site in list_sites(sites)}

	imported = import_site(archive, "gamma.localhost", sites_path=sites)
	assert imported["health"] == "ok"
	assert "gamma.localhost" in {site["site_name"] for site in list_sites(sites)}


def test_drop_site_archives_like_bench(tmp_path: Path) -> None:
	sites = tmp_path / "sites"
	create_site("drop.localhost", sites_path=sites)
	result = drop_site("drop.localhost", sites_path=sites)
	assert result["mode"] == "archived"
	assert Path(result["archive_path"]).exists()
	assert not (sites / "drop.localhost").exists()


def test_simple_app_names_resolve_to_frappe_org() -> None:
	assert resolve_app_source("crm") == {
		"app": "crm",
		"source": "https://github.com/frappe/crm.git",
		"kind": "frappe_org_name",
	}
	assert resolve_app_source("erpnext")["source"] == "https://github.com/frappe/erpnext.git"
	assert resolve_app_source("some-owner/some-app") == {
		"app": "some-app",
		"source": "https://github.com/some-owner/some-app.git",
		"kind": "github_slug",
	}
