import os
import unittest
from pathlib import Path
from unittest.mock import patch

from platform_paths import app_data_dir


class AppDataPathTests(unittest.TestCase):
    def test_windows_uses_local_and_roaming_app_data(self):
        with patch("platform_paths.sys.platform", "win32"), patch.dict(
            os.environ,
            {"LOCALAPPDATA": "C:/Local", "APPDATA": "C:/Roaming"},
            clear=True,
        ):
            self.assertEqual(app_data_dir(), Path("C:/Local/GitHubDesk"))
            self.assertEqual(
                app_data_dir(config=True), Path("C:/Roaming/GitHubDesk")
            )

    def test_macos_uses_application_support(self):
        with patch("platform_paths.sys.platform", "darwin"), patch(
            "platform_paths.Path.home", return_value=Path("/Users/test")
        ):
            self.assertEqual(
                app_data_dir(), Path("/Users/test/Library/Application Support/GitHubDesk")
            )
            self.assertEqual(
                app_data_dir(config=True),
                Path("/Users/test/Library/Application Support/GitHubDesk"),
            )

    def test_linux_honors_xdg_data_and_config_directories(self):
        with patch("platform_paths.sys.platform", "linux"), patch.dict(
            os.environ,
            {"XDG_DATA_HOME": "/tmp/data", "XDG_CONFIG_HOME": "/tmp/config"},
            clear=True,
        ):
            self.assertEqual(app_data_dir(), Path("/tmp/data/GitHubDesk"))
            self.assertEqual(
                app_data_dir(config=True), Path("/tmp/config/GitHubDesk")
            )


if __name__ == "__main__":
    unittest.main()
