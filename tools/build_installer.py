"""Build script to bundle dist/Blind-Spotter into a reusable single-file Windows installer.exe.
An Ashnif Arnob Product
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
APP_DIR = DIST_DIR / "Blind-Spotter"
TOOLS_DIR = PROJECT_ROOT / "tools"
PAYLOAD_ZIP = TOOLS_DIR / "app_payload.zip"


def create_payload_zip() -> Path:
    """Compress dist/Blind-Spotter directory into tools/app_payload.zip."""
    if not APP_DIR.exists():
        raise FileNotFoundError(f"Application directory not found: {APP_DIR}")

    print(f"Compressing {APP_DIR} into {PAYLOAD_ZIP}...")
    if PAYLOAD_ZIP.exists():
        PAYLOAD_ZIP.unlink()

    with zipfile.ZipFile(PAYLOAD_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(APP_DIR):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(APP_DIR)
                zf.write(file_path, str(rel_path))

    size_mb = PAYLOAD_ZIP.stat().st_size / (1024 * 1024)
    print(f"Payload zip created: {size_mb:.2f} MB")
    return PAYLOAD_ZIP


def compile_installer() -> None:
    """Compile tools/installer_gui.py into a standalone single-file installer.exe."""
    installer_gui = TOOLS_DIR / "installer_gui.py"
    icon_path = PROJECT_ROOT / "assets" / "icon.ico"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        f"--icon={icon_path}",
        f"--add-data={PAYLOAD_ZIP};.",
        f"--add-data={icon_path};assets",
        "--name=installer",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(PROJECT_ROOT / "build" / "installer"),
        str(installer_gui),
    ]

    print("Compiling installer executable with PyInstaller...")
    print("Command:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller failed with code {res.returncode}")

    installer_exe = DIST_DIR / "installer.exe"
    setup_exe = DIST_DIR / "Blind-Spotter-Setup.exe"

    if installer_exe.exists():
        shutil.copy2(installer_exe, setup_exe)
        size_mb = installer_exe.stat().st_size / (1024 * 1024)
        print(f"SUCCESS: Created standalone installer:")
        print(f"  - {installer_exe} ({size_mb:.2f} MB)")
        print(f"  - {setup_exe} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    create_payload_zip()
    compile_installer()
