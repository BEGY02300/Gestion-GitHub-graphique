from __future__ import annotations

import base64
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from github_api import GitHub, GitHubError
from local_cache import LocalCache
from mcp_client import MCPClientManager, MCPError


class DesktopApi:
    def __init__(self) -> None:
        self.github: GitHub | None = None
        self.cache = LocalCache()
        self.cached_profile: dict[str, Any] = {}
        self.mcp = MCPClientManager()

    def _invoke(self, operation: Callable[..., Any], *args: Any) -> dict[str, Any]:
        try:
            if self.github is None:
                raise GitHubError("Connecte-toi avec GitHub CLI puis actualise l'application.")
            data = operation(self.github, *args)
            if (
                isinstance(data, dict)
                and data.get("name")
                and ("full_name" in data or "private" in data or "isPrivate" in data)
            ):
                self.github.update_cached_repository(data)
                self._save_cached_snapshot()
            return {"ok": True, "data": data}
        except GitHubError as error:
            return {"ok": False, "error": str(error)}
        except (OSError, sqlite3.Error, ValueError) as error:
            return {"ok": False, "error": f"Erreur de cache local : {error}"}

    def connect(self) -> dict[str, Any]:
        try:
            self.github = GitHub(load_initial_data=False)
            snapshot = self.cache.load_snapshot()
            if snapshot is not None:
                self.cached_profile = snapshot["profile"]
                self.github.load_cached_data(
                    snapshot["profile"], snapshot["repositories"]
                )
            return {
                "ok": True,
                "data": {
                    "owner": self.github.owner,
                    "profile": self.cached_profile,
                    "repositories": self.github.repositories(),
                    "cached_at": snapshot["cached_at"] if snapshot else "",
                    "has_cache": snapshot is not None,
                },
            }
        except GitHubError as error:
            return {"ok": False, "error": str(error)}
        except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
            return {"ok": False, "error": f"Erreur de cache local : {error}"}

    def sync_github(self) -> dict[str, Any]:
        try:
            if self.github is None:
                self.github = GitHub(load_initial_data=False)
            profile, repositories = self.github.refresh_initial_data()
            warnings: list[str] = []
            cached_avatar = str(self.cached_profile.get("avatarDataUrl") or "")
            same_avatar = (
                profile.get("avatarUrl")
                and profile.get("avatarUrl") == self.cached_profile.get("avatarUrl")
            )
            if same_avatar and cached_avatar.startswith("data:image/"):
                profile["avatarDataUrl"] = cached_avatar
            elif profile.get("avatarUrl"):
                avatar, mime_type, warning = self._download_avatar(profile["avatarUrl"])
                if avatar:
                    profile["avatar_data"] = avatar
                    profile["avatar_mime"] = mime_type
                    profile["avatarDataUrl"] = (
                        f"data:{mime_type};base64,"
                        f"{base64.b64encode(avatar).decode('ascii')}"
                    )
                elif cached_avatar.startswith("data:image/"):
                    profile["avatarDataUrl"] = cached_avatar
                    profile["avatarUrl"] = self.cached_profile.get("avatarUrl", "")
                if warning:
                    warnings.append(warning)
            result = self.cache.save_snapshot(profile, repositories)
            saved = self.cache.load_snapshot()
            if saved is None:
                raise GitHubError("La copie locale du compte n'a pas pu etre relue.")
            self.cached_profile = saved["profile"]
            self.github.load_cached_data(
                saved["profile"], saved["repositories"]
            )
            return {
                "ok": True,
                "data": {
                    "owner": result["owner"],
                    "profile": saved["profile"],
                    "repositories": saved["repositories"],
                    "cached_at": saved["cached_at"],
                    "changed": result["changed"],
                    "removed": result["removed"],
                    "warnings": warnings,
                },
            }
        except GitHubError as error:
            return {"ok": False, "error": str(error)}
        except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
            return {"ok": False, "error": f"Erreur de cache local : {error}"}

    @staticmethod
    def _download_avatar(url: str) -> tuple[bytes | None, str | None, str | None]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "avatars.githubusercontent.com":
            return None, None, "L’avatar GitHub a une adresse inattendue et n’a pas été téléchargé."
        try:
            request = Request(url, headers={"User-Agent": "GitHub-Desk"})
            with urlopen(request, timeout=8) as response:
                mime_type = response.headers.get_content_type()
                if not mime_type.startswith("image/"):
                    return None, None, "La réponse de l’avatar n’est pas une image."
                data = response.read(2_000_001)
        except (OSError, URLError, TimeoutError) as error:
            return None, None, f"Avatar non téléchargé : {error}"
        if len(data) > 2_000_000:
            return None, None, "L’image de profil dépasse la taille maximale de 2 Mo."
        return data, mime_type, None

    def _save_cached_snapshot(self) -> None:
        if self.github is None or not self.cached_profile or not self.github.owner:
            return
        self.cache.save_snapshot(
            self.cached_profile,
            self.github.repositories(),
            synchronized=False,
        )

    def _cached_invoke(
        self,
        key: str,
        operation: Callable[..., Any],
        *args: Any,
        refresh: bool = False,
    ) -> dict[str, Any]:
        try:
            if not refresh:
                cached = self.cache.get_resource(key)
                if cached is not None:
                    return {"ok": True, "data": cached["data"], "cached": True}
            result = self._invoke(operation, *args)
            if result["ok"]:
                self.cache.set_resource(key, result["data"])
                result["cached"] = False
            return result
        except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
            return {"ok": False, "error": f"Erreur de cache local : {error}"}

    def _invalidate_repository_cache(self, repository: str) -> None:
        if self.github is not None:
            self.cache.delete_resources(f"{self.github.owner}/{repository}/")

    def repositories(self) -> dict[str, Any]:
        result = self._invoke(lambda github: github.repositories())
        if result["ok"]:
            self._save_cached_snapshot()
        return result

    def stats(self) -> dict[str, Any]:
        return self._invoke(lambda github: github.stats())

    def repository(self, name: str, refresh: bool = False) -> dict[str, Any]:
        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{name}/details",
            lambda github: github.repository(name),
            refresh=refresh,
        )

    def repository_readme(
        self, name: str, refresh: bool = False
    ) -> dict[str, Any]:
        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{name}/readme",
            lambda github: github.repository_readme(name),
            refresh=refresh,
        )

    def local_favorites(self) -> dict[str, Any]:
        try:
            cached = self.cache.get_resource("preferences/favorites")
            return {"ok": True, "data": cached["data"] if cached else []}
        except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
            return {"ok": False, "error": f"Erreur de cache local : {error}"}

    def set_local_favorites(self, names: list[str]) -> dict[str, Any]:
        if not isinstance(names, list) or not all(
            isinstance(name, str) for name in names
        ):
            return {"ok": False, "error": "La liste des favoris est invalide."}
        favorites = sorted(
            {name.strip() for name in names if name.strip()}, key=str.casefold
        )
        try:
            self.cache.set_resource("preferences/favorites", favorites)
            return {"ok": True, "data": favorites}
        except (OSError, sqlite3.Error, ValueError) as error:
            return {"ok": False, "error": f"Erreur de cache local : {error}"}

    def open_external(self, url: str) -> dict[str, Any]:
        def open_link(github: GitHub) -> str:
            if not github.open_external(url):
                raise GitHubError("Le navigateur par defaut n'a pas pu ouvrir ce lien.")
            return "Lien ouvert dans le navigateur."

        return self._invoke(open_link)

    def create_repository(
        self,
        name: str,
        description: str,
        visibility: str,
        initialize: bool,
        template: str = "blank",
    ) -> dict[str, Any]:
        return self._invoke(
            lambda github: github.create_repository(
                name, description, visibility, initialize, template
            )
        )

    def create_from_github_template(
        self, name: str, description: str, visibility: str, template_repository: str
    ) -> dict[str, Any]:
        return self._invoke(
            lambda github: github.create_from_github_template(
                name, description, visibility, template_repository
            )
        )

    @staticmethod
    def mcp_server_config() -> dict[str, Any]:
        server = Path(__file__).with_name("mcp_server.py").resolve()
        executable = Path(sys.executable)
        if executable.name.casefold() == "pythonw.exe":
            console_executable = executable.with_name("python.exe")
            if console_executable.is_file():
                executable = console_executable
        return {
            "ok": True,
            "data": {"command": str(executable), "args": ["-u", str(server)]},
        }

    def mcp_servers(self) -> dict[str, Any]:
        try:
            return {"ok": True, "data": self.mcp.servers()}
        except MCPError as error:
            return {"ok": False, "error": str(error)}

    def mcp_add_server(
        self, name: str, command: str, args: list[str]
    ) -> dict[str, Any]:
        try:
            return {"ok": True, "data": self.mcp.add_server(name, command, args)}
        except MCPError as error:
            return {"ok": False, "error": str(error)}

    def mcp_remove_server(self, name: str) -> dict[str, Any]:
        try:
            self.mcp.remove_server(name)
            return {"ok": True, "data": True}
        except MCPError as error:
            return {"ok": False, "error": str(error)}

    def mcp_disconnect(self, name: str) -> dict[str, Any]:
        try:
            self.mcp.disconnect(name)
            return {"ok": True, "data": True}
        except MCPError as error:
            return {"ok": False, "error": str(error)}

    def mcp_connect(self, name: str) -> dict[str, Any]:
        try:
            return {"ok": True, "data": self.mcp.connect(name)}
        except MCPError as error:
            return {"ok": False, "error": str(error)}

    def mcp_tools(self, name: str) -> dict[str, Any]:
        try:
            return {"ok": True, "data": self.mcp.tools(name)}
        except MCPError as error:
            return {"ok": False, "error": str(error)}

    def mcp_call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            return {
                "ok": True,
                "data": self.mcp.call_tool(server_name, tool_name, arguments),
            }
        except MCPError as error:
            return {"ok": False, "error": str(error)}

    def update_repository(self, name: str, updates: dict[str, Any]) -> dict[str, Any]:
        result = self._invoke(lambda github: github.update_repository(name, updates))
        if result["ok"]:
            if self.github is not None and updates.get("name") and updates["name"] != name:
                self.github.remove_cached_repository(name)
                self._save_cached_snapshot()
            self._invalidate_repository_cache(name)
            renamed = updates.get("name")
            if isinstance(renamed, str) and renamed and renamed != name:
                self._invalidate_repository_cache(renamed)
        return result

    def repository_topics(
        self, name: str, refresh: bool = False
    ) -> dict[str, Any]:
        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{name}/topics",
            lambda github: github.repository_topics(name),
            refresh=refresh,
        )

    def update_repository_topics(self, name: str, topics: list[str]) -> dict[str, Any]:
        result = self._invoke(
            lambda github: github.update_repository_topics(name, topics)
        )
        if result["ok"]:
            self._invalidate_repository_cache(name)
        return result

    def vulnerability_alerts_enabled(
        self, name: str, refresh: bool = False
    ) -> dict[str, Any]:
        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{name}/vulnerability-alerts",
            lambda github: github.vulnerability_alerts_enabled(name),
            refresh=refresh,
        )

    def set_vulnerability_alerts(
        self, name: str, enabled: bool
    ) -> dict[str, Any]:
        result = self._invoke(
            lambda github: github.set_vulnerability_alerts(name, enabled)
        )
        if result["ok"]:
            self._invalidate_repository_cache(name)
        return result

    def collaborators(self, name: str, refresh: bool = False) -> dict[str, Any]:
        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{name}/collaborators",
            lambda github: github.collaborators(name),
            refresh=refresh,
        )

    def invite_collaborator(
        self, name: str, username: str, permission: str
    ) -> dict[str, Any]:
        result = self._invoke(
            lambda github: github.invite_collaborator(name, username, permission)
        )
        if result["ok"]:
            self._invalidate_repository_cache(name)
        return result

    def remove_collaborator(
        self, name: str, username: str, confirmation: str
    ) -> dict[str, Any]:
        def remove(github: GitHub) -> str:
            if confirmation != f"RETIRER {username}":
                raise GitHubError("Confirmation incorrecte. Collaborateur conserve.")
            github.remove_collaborator(name, username)
            return f"Acces de {username} retire."

        result = self._invoke(remove)
        if result["ok"]:
            self._invalidate_repository_cache(name)
        return result

    def set_archived(self, name: str, archived: bool) -> dict[str, Any]:
        result = self._invoke(lambda github: github.set_archived(name, archived))
        if result["ok"]:
            self._invalidate_repository_cache(name)
        return result

    def delete_repository(self, name: str, confirmation: str) -> dict[str, Any]:
        def delete(github: GitHub) -> str:
            expected = f"SUPPRIMER {github.owner}/{name}"
            if confirmation != expected:
                raise GitHubError("Confirmation incorrecte. Depot non supprime.")
            github.delete_repository(name)
            github.remove_cached_repository(name)
            return f"{github.owner}/{name} supprime."

        result = self._invoke(delete)
        if result["ok"]:
            self._save_cached_snapshot()
            self._invalidate_repository_cache(name)
        return result

    def archive_snapshot(self, name: str, archive_name: str) -> dict[str, Any]:
        return self._invoke(lambda github: github.archive_snapshot(name, archive_name))

    def branches(self, repo: str, refresh: bool = False) -> dict[str, Any]:
        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{repo}/branches",
            lambda github: github.branches(repo),
            refresh=refresh,
        )

    def create_branch(self, repo: str, name: str, source: str) -> dict[str, Any]:
        result = self._invoke(lambda github: github.create_branch(repo, name, source))
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result

    def rename_branch(
        self, repo: str, old_name: str, new_name: str
    ) -> dict[str, Any]:
        result = self._invoke(lambda github: github.rename_branch(repo, old_name, new_name))
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result

    def delete_branch(
        self, repo: str, name: str, confirmation: str
    ) -> dict[str, Any]:
        def delete(github: GitHub) -> str:
            if confirmation != f"SUPPRIMER {name}":
                raise GitHubError("Confirmation incorrecte. Branche non supprimee.")
            github.delete_branch(repo, name)
            return f"Branche {name} supprimee."

        result = self._invoke(delete)
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result

    def pull_requests(self, repo: str, refresh: bool = False) -> dict[str, Any]:
        def list_pulls(github: GitHub) -> list[dict[str, Any]]:
            pulls = github.pull_requests(repo)
            for pull in pulls:
                pull["safeToMerge"] = (
                    pull.get("state") == "OPEN"
                    and pull.get("mergeable") == "MERGEABLE"
                    and pull.get("mergeStateStatus") == "CLEAN"
                    and not pull.get("isDraft")
                    and pull.get("reviewDecision") != "REVIEW_REQUIRED"
                )
            return pulls

        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{repo}/pull-requests", list_pulls, refresh=refresh
        )

    def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool,
    ) -> dict[str, Any]:
        result = self._invoke(
            lambda github: github.create_pull_request(
                repo, title, body, head, base, draft
            )
        )
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result

    def close_pull_request(
        self, repo: str, number: int, confirmation: str
    ) -> dict[str, Any]:
        def close(github: GitHub) -> dict[str, Any]:
            if confirmation != f"FERMER PR {number}":
                raise GitHubError("Confirmation incorrecte. Pull request non fermee.")
            return github.close_pull_request(repo, number)

        result = self._invoke(close)
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result

    def merge_pull_request(
        self, repo: str, number: int, method: str, confirmation: str
    ) -> dict[str, Any]:
        def merge(github: GitHub) -> dict[str, Any]:
            if confirmation != f"FUSIONNER PR {number}":
                raise GitHubError("Confirmation incorrecte. Pull request non fusionnee.")
            return github.merge_pull_request(repo, number, method)

        result = self._invoke(merge)
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result

    def issues(self, repo: str, refresh: bool = False) -> dict[str, Any]:
        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{repo}/issues",
            lambda github: github.issues(repo),
            refresh=refresh,
        )

    def create_issue(self, repo: str, title: str, body: str) -> dict[str, Any]:
        result = self._invoke(lambda github: github.create_issue(repo, title, body))
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result

    def update_issue(
        self,
        repo: str,
        number: int,
        title: str,
        body: str,
        state: str,
        confirmation: str,
    ) -> dict[str, Any]:
        def update(github: GitHub) -> dict[str, Any]:
            if state == "closed" and confirmation != f"FERMER ISSUE {number}":
                raise GitHubError("Confirmation incorrecte. Issue non fermee.")
            return github.update_issue(repo, number, title, body, state)

        result = self._invoke(update)
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result

    def workflows(self, repo: str, refresh: bool = False) -> dict[str, Any]:
        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{repo}/workflows",
            lambda github: github.workflows(repo),
            refresh=refresh,
        )

    def workflow_runs(self, repo: str, refresh: bool = False) -> dict[str, Any]:
        owner = self.github.owner if self.github else ""
        return self._cached_invoke(
            f"{owner}/{repo}/workflow-runs",
            lambda github: github.workflow_runs(repo),
            refresh=refresh,
        )

    def rerun_workflow(
        self, repo: str, run_id: int, confirmation: str
    ) -> dict[str, Any]:
        def rerun(github: GitHub) -> str:
            if confirmation != f"RELANCER {run_id}":
                raise GitHubError("Confirmation incorrecte. Workflow non relance.")
            github.rerun_workflow(repo, run_id)
            return f"Execution {run_id} relancee."

        result = self._invoke(rerun)
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result

    def cancel_workflow(
        self, repo: str, run_id: int, confirmation: str
    ) -> dict[str, Any]:
        def cancel(github: GitHub) -> str:
            if confirmation != f"ANNULER {run_id}":
                raise GitHubError("Confirmation incorrecte. Workflow non annule.")
            github.cancel_workflow(repo, run_id)
            return f"Execution {run_id} annulee."

        result = self._invoke(cancel)
        if result["ok"]:
            self._invalidate_repository_cache(repo)
        return result
