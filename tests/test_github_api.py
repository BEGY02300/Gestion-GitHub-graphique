import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_api import DesktopApi
from github_api import GitHub, GitHubError
from local_cache import LocalCache
from mcp_client import MCPClientManager, MCPServerClient
from mcp_server import handle_message


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

    def test_startup_loads_account_and_repositories_in_one_request(self):
        body = (
            '{"data":{"viewer":{"login":"test-owner","repositories":'
            '{"nodes":[{"name":"demo"}],"pageInfo":'
            '{"hasNextPage":false,"endCursor":null}}}}}'
        )
        response = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout=body, stderr=""
        )
        with patch("github_api.shutil.which", return_value="gh"), patch(
            "github_api.subprocess.run", return_value=response
        ) as run:
            github = GitHub()
        self.assertEqual(github.owner, "test-owner")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][:3], ["gh", "api", "graphql"])
        self.assertEqual(github.repositories(), [{"name": "demo"}])
        self.assertEqual(run.call_count, 1)

    def test_startup_follows_repository_pagination(self):
        pages = [
            '{"data":{"viewer":{"login":"test-owner","repositories":'
            '{"nodes":[{"name":"first"}],"pageInfo":'
            '{"hasNextPage":true,"endCursor":"cursor-1"}}}}}',
            '{"data":{"viewer":{"login":"test-owner","repositories":'
            '{"nodes":[{"name":"second"}],"pageInfo":'
            '{"hasNextPage":false,"endCursor":null}}}}}',
        ]
        completed = [
            subprocess.CompletedProcess(
                args=["gh"], returncode=0, stdout=page, stderr=""
            )
            for page in pages
        ]
        with patch("github_api.shutil.which", return_value="gh"), patch(
            "github_api.subprocess.run", side_effect=completed
        ) as run:
            github = GitHub()
        self.assertEqual(
            [repo["name"] for repo in github.repositories()], ["first", "second"]
        )
        self.assertEqual(run.call_count, 2)
        self.assertIn("endCursor=cursor-1", run.call_args.args[0])

    def test_api_serializes_boolean_as_a_typed_field(self):
        with patch.object(self.github, "_run", return_value='{"private":true}') as run:
            self.github._api(
                "POST", "user/repos", {"name": "demo", "private": True}
            )
        self.assertIn("--field", run.call_args.args[0])
        self.assertIn("private=true", run.call_args.args[0])
        self.assertIn("--raw-field", run.call_args.args[0])

    def test_python_template_creates_starter_files(self):
        created = {"name": "demo"}
        file_response = {"sha": "readme-sha"}
        with patch.object(
            self.github,
            "_api",
            side_effect=[created, file_response, {}, {}, {}, {}],
        ) as api, patch.object(self.github, "repository", return_value=created):
            result = self.github.create_repository(
                "demo", "description", "private", False, "python"
            )
        self.assertEqual(result, created)
        calls = api.call_args_list
        self.assertEqual(calls[0].args[0:2], ("POST", "user/repos"))
        self.assertTrue(calls[0].args[2]["auto_init"])
        self.assertEqual(len(calls), 6)
        readme_put = calls[2]
        self.assertEqual(readme_put.args[0], "PUT")
        self.assertEqual(readme_put.args[2]["sha"], "readme-sha")
        main_file = calls[3].args[2]["content"]
        self.assertIn("def main()", base64.b64decode(main_file).decode("utf-8"))

    def test_external_template_name_is_validated_before_request(self):
        with patch.object(self.github, "_api") as api:
            with self.assertRaisesRegex(GitHubError, "proprietaire/depot"):
                self.github.create_from_github_template(
                    "demo", "", "private", "not-a-valid-source"
                )
        api.assert_not_called()

    def test_external_template_creates_repository_from_valid_source(self):
        created = {"name": "new-project"}
        with patch.object(self.github, "_api", return_value=created) as api, patch.object(
            self.github, "repository", return_value=created
        ):
            result = self.github.create_from_github_template(
                "new-project", "description", "private", "octocat/hello-world"
            )
        self.assertEqual(result, created)
        self.assertEqual(
            api.call_args.args,
            (
                "POST",
                "repos/octocat/hello-world/generate",
                {
                    "owner": "test-owner",
                    "name": "new-project",
                    "description": "description",
                    "private": True,
                    "include_all_branches": False,
                },
            ),
        )

    def test_update_topics_sends_json_payload_and_normalizes_values(self):
        with patch.object(self.github, "_run", return_value='{"names":["python","web"]}') as run:
            result = self.github.update_repository_topics(
                "demo", [" Web ", "python", "web"]
            )
        self.assertEqual(result, ["python", "web"])
        self.assertEqual(run.call_args.args[0], [
            "api", "--method", "PUT", "repos/test-owner/demo/topics", "--input", "-"
        ])
        self.assertEqual(
            json.loads(run.call_args.kwargs["input_text"]),
            {"names": ["python", "web"]},
        )

    def test_invalid_topic_does_not_call_github(self):
        with patch.object(self.github, "_api_json") as api:
            with self.assertRaisesRegex(GitHubError, "sujet"):
                self.github.update_repository_topics("demo", ["Not valid!"])
        api.assert_not_called()

    def test_disabled_vulnerability_alerts_are_recognized_without_hiding_forbidden(self):
        with patch.object(
            self.github, "_run", side_effect=GitHubError("HTTP 404: Not Found")
        ):
            self.assertFalse(self.github.vulnerability_alerts_enabled("demo"))
        with patch.object(
            self.github, "_run", side_effect=GitHubError("HTTP 403: Forbidden")
        ):
            with self.assertRaisesRegex(GitHubError, "403"):
                self.github.vulnerability_alerts_enabled("demo")

    def test_inviting_collaborator_validates_user_and_permission(self):
        with patch.object(self.github, "_api", return_value={}) as api:
            self.github.invite_collaborator("demo", "valid-user", "push")
        self.assertEqual(
            api.call_args.args[1:],
            (
                "repos/test-owner/demo/collaborators/valid-user",
                {"permission": "push"},
            ),
        )
        with patch.object(self.github, "_api") as api:
            with self.assertRaisesRegex(GitHubError, "Nom d'utilisateur"):
                self.github.invite_collaborator("demo", "bad--user-", "push")
        api.assert_not_called()

    def test_mcp_server_exposes_read_only_tool_catalog(self):
        response = handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
        tools = response["result"]["tools"]
        self.assertTrue(tools)
        self.assertTrue(all(tool["name"].startswith("github_") for tool in tools))
        self.assertNotIn("delete_repository", {tool["name"] for tool in tools})

    def test_mcp_server_tool_call_returns_structured_data(self):
        with patch("mcp_server._call_tool", return_value=[{"name": "demo"}]):
            response = handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "github_list_repositories", "arguments": {}},
                }
            )
        self.assertEqual(response["result"]["structuredContent"]["result"], [{"name": "demo"}])

    def test_mcp_stdio_client_initializes_lists_and_calls_tools(self):
        server = (
            "import json,sys\n"
            "for line in sys.stdin:\n"
            " m=json.loads(line); method=m.get('method'); rid=m.get('id')\n"
            " if rid is None: continue\n"
            " if method=='initialize': result={'protocolVersion':'2025-03-26','capabilities':{'tools':{}},'serverInfo':{'name':'fake','version':'1'}}\n"
            " elif method=='tools/list': result={'tools':[{'name':'echo','inputSchema':{'type':'object'}}]}\n"
            " elif method=='tools/call': result={'content':[{'type':'text','text':json.dumps(m['params']['arguments'])}]}\n"
            " else: result={}\n"
            " print(json.dumps({'jsonrpc':'2.0','id':rid,'result':result}),flush=True)\n"
        )
        client = MCPServerClient(sys.executable, ["-u", "-c", server])
        try:
            tools = client.list_tools()
            result = client.call_tool("echo", {"hello": "world"})
        finally:
            client.close()
        self.assertEqual(tools[0]["name"], "echo")
        self.assertEqual(json.loads(result["content"][0]["text"]), {"hello": "world"})

    def test_mcp_server_configuration_is_saved_without_starting_process(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"APPDATA": directory}
        ):
            manager = MCPClientManager()
            manager.add_server("local-test", sys.executable, ["-u", "server.py"])
            servers = manager.servers()
        self.assertEqual(servers[0]["name"], "local-test")
        self.assertFalse(servers[0]["connected"])

    def test_repository_branch_lists_use_local_cache_until_explicit_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = LocalCache(Path(directory) / "cache.sqlite3")
            api = DesktopApi.__new__(DesktopApi)
            api.cache = cache
            api.cached_profile = {}
            api.github = self.github
            cache.set_resource("test-owner/demo/branches", [{"name": "cached"}])
            with patch.object(
                self.github, "branches", return_value=[{"name": "live"}]
            ) as request:
                cached = api.branches("demo")
                fresh = api.branches("demo", True)
        self.assertEqual(cached["data"], [{"name": "cached"}])
        self.assertEqual(fresh["data"], [{"name": "live"}])
        request.assert_called_once_with("demo")

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
        with patch("app_api.LocalCache"):
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
