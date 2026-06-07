# -*- mode: python ; coding: utf-8 -*-
import os
import sysconfig
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

ROOT = Path.cwd()
RUNTIME_DIR = ROOT / "desktop" / "runtime"

datas, binaries, hiddenimports = [], [], []

pd, pb, ph = collect_all("frappe")
datas += pd
binaries += pb
hiddenimports += ph

for src, dest in [
    ("frappe", "frappe"),
    ("sites/assets", "sites/assets"),
    ("desktop/runtime/resources", "resources"),
    ("desktop/runtime/resources/seed_site/sites/assets", "assets"),
]:
    p = ROOT / src
    if p.exists():
        datas.append((str(p), dest))

assets_path = ROOT / "sites" / "assets"
if assets_path.exists():
    datas.append((str(assets_path), "assets"))

for package in ["semantic_version", "setuptools"]:
    try:
        datas += copy_metadata(package)
    except Exception:
        pass

hiddenimports += collect_submodules("frappe")
hiddenimports += collect_submodules("passlib.handlers")
hiddenimports += [
    "frappe.database.sqlite",
    "frappe.utils.redis_wrapper",
    "frappe.app",
    "pkg_resources",
    "semantic_version",
    "setuptools",
    "werkzeug",
]

site_packages = Path(sysconfig.get_paths().get("purelib", ""))
pathex = [str(ROOT), str(site_packages)] if site_packages else [str(ROOT)]

a = Analysis(
    [str(RUNTIME_DIR / "runner" / "main.py")],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(RUNTIME_DIR / "pyinstaller" / "hooks")],
    excludes=["tkinter", "pytest", "IPython", "matplotlib", "numpy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="frappe-sqlite",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="frappe-sqlite-macos",
)
