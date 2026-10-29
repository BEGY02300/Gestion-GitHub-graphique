from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir(*, config: bool = False) -> Path:
    if sys.platform == "win32":
        variable = "APPDATA" if config else "LOCALAPPDATA"
        value = os.environ.get(variable)
        base = (
            Path(value)
            if value
            else Path.home() / "AppData" / ("Roaming" if config else "Local")
        )
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        variable = "XDG_CONFIG_HOME" if config else "XDG_DATA_HOME"
        value = os.environ.get(variable)
        base = (
            Path(value)
            if value
            else Path.home() / (".config" if config else ".local/share")
        )
    return base / "GitHubDesk"
