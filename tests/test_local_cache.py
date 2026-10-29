import base64
import tempfile
import unittest
from pathlib import Path

from local_cache import LocalCache


class LocalCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.cache = LocalCache(Path(self.temporary_directory.name) / "cache.sqlite3")

    def test_snapshot_is_local_and_reports_only_changed_repositories(self):
        profile = {
            "login": "test-owner",
            "name": "Test Owner",
            "avatarUrl": "https://avatars.githubusercontent.com/u/123",
            "avatar_mime": "image/png",
            "avatar_data": b"avatar-bytes",
        }
        repositories = [
            {"name": "alpha", "updatedAt": "2026-10-29T10:00:00Z"},
            {"name": "beta", "updatedAt": "2026-10-29T10:00:00Z"},
        ]
        first = self.cache.save_snapshot(profile, repositories)
        self.assertEqual(first["changed"], ["alpha", "beta"])
        second = self.cache.save_snapshot(profile, repositories)
        self.assertEqual(second["changed"], [])
        self.assertEqual(second["removed"], [])

        updated = self.cache.save_snapshot(
            profile,
            [
                {"name": "alpha", "updatedAt": "2026-10-29T11:00:00Z"},
                repositories[1],
            ],
        )
        self.assertEqual(updated["changed"], ["alpha"])
        self.assertEqual(updated["removed"], [])

        snapshot = self.cache.load_snapshot()
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["owner"], "test-owner")
        self.assertEqual(
            snapshot["profile"]["avatarDataUrl"],
            "data:image/png;base64,"
            + base64.b64encode(b"avatar-bytes").decode("ascii"),
        )
        self.assertEqual(snapshot["repositories"][0]["updatedAt"], "2026-10-29T11:00:00Z")

    def test_resources_are_cached_and_can_be_invalidated_per_repository(self):
        self.cache.set_resource("test-owner/demo/issues", [{"number": 2}])
        self.cache.set_resource("test-owner/other/issues", [{"number": 9}])

        cached = self.cache.get_resource("test-owner/demo/issues")
        self.assertEqual(cached["data"], [{"number": 2}])
        self.assertTrue(cached["cached_at"])

        self.cache.delete_resources("test-owner/demo/")
        self.assertIsNone(self.cache.get_resource("test-owner/demo/issues"))
        self.assertEqual(
            self.cache.get_resource("test-owner/other/issues")["data"],
            [{"number": 9}],
        )

    def test_snapshot_removes_repositories_deleted_on_github(self):
        profile = {"login": "test-owner"}
        self.cache.save_snapshot(
            profile, [{"name": "keep"}, {"name": "gone"}]
        )
        result = self.cache.save_snapshot(profile, [{"name": "keep"}])
        self.assertEqual(result["removed"], ["gone"])
        self.assertEqual(
            [repo["name"] for repo in self.cache.load_snapshot()["repositories"]],
            ["keep"],
        )


if __name__ == "__main__":
    unittest.main()
