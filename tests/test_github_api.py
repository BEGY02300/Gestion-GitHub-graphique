import subprocess
import unittest
from unittest.mock import patch

from app_api import DesktopApi
from github_api import GitHub, GitHubError


class GitHubTests(unittest.TestCase):
    def setUp(self):
        self.github = GitHub.__new__(GitHub)
        self.github.owner = "test-owner"

    def test_api_uses_utf8_safe_gh_run(self):
        completed = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="ok", stderr=""
        )
        with patch("github_api.subprocess.run", return_value=completed) as run:
            result = self.github._run(["api", "user"], "lecture utilisateur")
        self.assertEqual(result, "ok")
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_api_serializes_boolean_as_a_typed_field(self):
        with patch.object(self.github, "_run", return_value='{"private":true}') as run:
            self.github._api(
                "POST", "user/repos", {"name": "demo", "private": True}
            )
        self.assertIn("--field", run.call_args.args[0])
        self.assertIn("private=true", run.call_args.args[0])
        self.assertIn("--raw-field", run.call_args.args[0])

    def test_default_branch_cannot_be_deleted(self):
        with patch.object(
            self.github, "repository", return_value={"default_branch": "main"}
        ), patch.object(self.github, "_api") as api:
            with self.assertRaisesRegex(GitHubError, "branche par defaut"):
                self.github.delete_branch("project", "main")
        api.assert_not_called()

    def test_protected_branch_cannot_be_deleted(self):
        with patch.object(
            self.github, "repository", return_value={"default_branch": "main"}
        ), patch.object(
            self.github,
            "branches",
            return_value=[{"name": "release", "protected": True}],
        ), patch.object(self.github, "_api") as api:
            with self.assertRaisesRegex(GitHubError, "protegee"):
                self.github.delete_branch("project", "release")
        api.assert_not_called()

    def test_unprotected_branch_can_be_deleted(self):
        with patch.object(
            self.github, "repository", return_value={"default_branch": "main"}
        ), patch.object(
            self.github,
            "branches",
            return_value=[{"name": "feature", "protected": False}],
        ), patch.object(self.github, "_api", return_value="") as api:
            self.github.delete_branch("project", "feature")
        self.assertEqual(
            api.call_args.args,
            (
                "DELETE",
                "repos/test-owner/project/git/refs/heads/feature",
            ),
        )

    def test_merge_requires_github_clean_state(self):
        pull = {
            "number": 7,
            "state": "OPEN",
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "BLOCKED",
            "isDraft": False,
            "reviewDecision": "APPROVED",
        }
        with patch.object(self.github, "pull_requests", return_value=[pull]), patch.object(
            self.github, "_api"
        ) as api:
            with self.assertRaisesRegex(GitHubError, "ne signale pas"):
                self.github.merge_pull_request("project", 7, "squash")
        api.assert_not_called()

    def test_private_archive_required_for_snapshot(self):
        with patch.object(self.github, "repository", return_value={"private": False}):
            with self.assertRaisesRegex(GitHubError, "n'est pas prive"):
                self.github.ensure_private_archive("archive")

    def test_missing_archive_is_created_private_and_initialized(self):
        with patch.object(
            self.github, "repository", side_effect=GitHubError("HTTP 404: Not Found")
        ), patch.object(
            self.github,
            "create_repository",
            return_value={"private": True},
        ) as create:
            result = self.github.ensure_private_archive("archive")
        self.assertTrue(result["private"])
        create.assert_called_once_with(
            "archive",
            "Archive privee des projets GitHub",
            "private",
            initialize=True,
        )

    def test_archive_creation_does_not_hide_non_404_errors(self):
        with patch.object(
            self.github,
            "repository",
            side_effect=GitHubError("HTTP 403: Forbidden"),
        ), patch.object(self.github, "create_repository") as create:
            with self.assertRaisesRegex(GitHubError, "403"):
                self.github.ensure_private_archive("archive")
        create.assert_not_called()

    def test_delete_bridge_requires_exact_repository_confirmation(self):
        api = DesktopApi()
        api.github = self.github
        with patch.object(self.github, "delete_repository") as delete:
            result = api.delete_repository("demo", "SUPPRIMER autre/demo")
        self.assertFalse(result["ok"])
        delete.assert_not_called()

    def test_external_links_are_restricted_to_github(self):
        with self.assertRaisesRegex(GitHubError, "HTTPS GitHub"):
            self.github.open_external("https://example.com/")


if __name__ == "__main__":
    unittest.main()
