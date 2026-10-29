from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from PyInstaller.__main__ import run as run_pyinstaller


ROOT = Path(__file__).resolve().parents[1]


def run() -> Path:
    os.chdir(ROOT)
    subprocess.run([sys.executable, "tools/build_assets.py"], check=True)
    build_assets = ROOT / "build" / "assets"
    system = platform.system()
    app_name = "GitHub Desk" if system == "Darwin" else "GitHubDesk"
    icon = {
        "Windows": build_assets / "github-desk.ico",
        "Darwin": build_assets / "github-desk.icns",
        "Linux": build_assets / "github-desk.png",
    }.get(system)
    if icon is None:
        raise RuntimeError(f"Plateforme non prise en charge : {system}")
    if system == "Darwin":
        subprocess.run(
            [
                "iconutil",
                "-c",
                "icns",
                str(build_assets / "github-desk.iconset"),
                "-o",
                str(icon),
            ],
            check=True,
        )

    separator = os.pathsep
    data = [
        f"{ROOT / 'interface.html'}{separator}.",
        f"{ROOT / 'assets' / 'github-desk.svg'}{separator}assets",
    ]
    arguments = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        app_name,
        "--icon",
        str(icon),
        "--collect-all",
        "webview",
        "--add-data",
        data[0],
        "--add-data",
        data[1],
    ]
    backend = {
        "Windows": "webview.platforms.edgechromium",
        "Darwin": "webview.platforms.cocoa",
        "Linux": "webview.platforms.gtk",
    }[system]
    arguments.extend(["--hidden-import", backend, str(ROOT / "1.py")])
    run_pyinstaller(arguments)

    dist = ROOT / "dist"
    app_dir = dist / app_name
    if system == "Darwin":
        app_dir = dist / f"{app_name}.app"
    if not app_dir.exists():
        raise FileNotFoundError(f"PyInstaller n'a pas créé l'application : {app_dir}")
    shutil.copy2(ROOT / "README.md", app_dir.parent / "README.md")

    archive_name = {
        "Windows": "github-desk-windows-x64.zip",
        "Darwin": f"github-desk-macos-{platform.machine().lower()}.zip",
        "Linux": "github-desk-linux-x64.tar.gz",
    }[system]
    archive = dist / archive_name
    archive_root = dist / "package"
    if archive_root.exists():
        shutil.rmtree(archive_root)
    archive_root.mkdir()
    shutil.copytree(app_dir, archive_root / app_dir.name)
    shutil.copy2(ROOT / "README.md", archive_root / "README.md")
    archive_base = archive.with_suffix("")
    if system == "Linux":
        archive_base = archive_base.with_suffix("")
    shutil.make_archive(
        str(archive_base),
        "gztar" if system == "Linux" else "zip",
        root_dir=archive_root,
    )
    shutil.rmtree(archive_root)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sums = dist / f"SHA256SUMS-{system.lower()}.txt"
    with sums.open("w", encoding="utf-8", newline="\n") as file:
        file.write(f"{digest}  {archive.name}\n")
    print(f"Paquet créé : {archive}")
    return archive


if __name__ == "__main__":
    run()
