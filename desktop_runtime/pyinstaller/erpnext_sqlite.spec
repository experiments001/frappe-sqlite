# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path.cwd()

datas, binaries, hiddenimports = [], [], []

pd, pb, ph = collect_all("frappe")
datas += pd; binaries += pb; hiddenimports += ph

for src, dest in [
    ("apps/frappe", "apps/frappe"),
    ("sites/assets", "sites/assets"),
    ("desktop_runtime/resources", "resources"),
]:
    p = ROOT / src
    if p.exists():
        datas.append((str(p), dest))

# Also include the assets symlink target as direct assets for frozen mode
assets_path = ROOT / "sites" / "assets"
if assets_path.exists():
    datas.append((str(assets_path), "assets"))

hiddenimports += collect_submodules("frappe")
hiddenimports += [
    "frappe.database.sqlite",
    "frappe.utils.redis_wrapper",
    "frappe.app",
    "werkzeug",
]
hiddenimports += collect_submodules("passlib.handlers")

a = Analysis(
    [str(ROOT / "desktop_runtime" / "runner" / "main.py")],
    pathex=[str(ROOT), str(ROOT/"apps"/"frappe"), str(ROOT/".venv-macos"/"lib"/"python3.14"/"site-packages")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["desktop_runtime/pyinstaller/hooks"],
    excludes=["tkinter", "pytest", "IPython", "matplotlib", "numpy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="frappe-sqlite",
    debug=False, strip=False, upx=False, console=True,
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="frappe-sqlite-macos",
)
