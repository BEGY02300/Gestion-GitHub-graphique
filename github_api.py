from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import quote


class GitHubError(RuntimeError):
    pass


class GitHub:
    def __init__(self) -> None:
        if shutil.which("gh") is None:
            raise GitHubError(
                "GitHub CLI (gh) est introuvable. Lance "
                "Nouveau Fichier source Python.bat pour l'installer."
            )
        self._run(["auth", "status"], "verification de la connexion")
        self.owner = self._run(["api", "user", "--jq", ".login"], "lecture du compte")
        if not self.owner:
            raise GitHubError("Impossible de trouver le compte GitHub connecte.")

    def _run(
        self,
        args: list[str],
        description: str,
        *,
        cwd: Path | None = None,
        timeout: int = 120,
    ) -> str:
        try:
            result = subprocess.run(
                ["gh", *args],
                cwd=cwd,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except FileNotFoundError as error:
            raise GitHubError("GitHub CLI (gh) est introuvable.") from error
        except subprocess.TimeoutExpired as error:
            raise GitHubError(f"Delai depasse pendant {description}.") from error
        if result.returncode:
            detail = (result.stderr or result.stdout or "").strip()
            raise GitHubError(detail or f"Echec pendant {description}.")
        return (result.stdout or "").strip()

    @staticmethod
    def _git(
        args: list[str], description: str, *, cwd: Path, timeout: int = 120
    ) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=cwd,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except FileNotFoundError as error:
            raise GitHubError("Git est introuvable.") from error
        except subprocess.TimeoutExpired as error:
            raise GitHubError(f"Delai depasse pendant {description}.") from error
        if result.returncode:
            detail = (result.stderr or result.stdout or "").strip()
            raise GitHubError(detail or f"Echec pendant {description}.")
        return (result.stdout or "").strip()

    @staticmethod
    def _json(raw: str, description: str) -> Any:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise GitHubError(f"Reponse GitHub invalide pendant {description}.") from error

    def _api(
        self,
        method: str,
        endpoint: str,
        fields: dict[str, Any] | None = None,
        *,
        json_response: bool = True,
    ) -> Any:
        args = ["api", "--method", method, endpoint]
        for key, value in (fields or {}).items():
            if isinstance(value, bool):
                args.extend(["--field", f"{key}={'true' if value else 'false'}"])
            elif isinstance(value, int):
                args.extend(["--field", f"{key}={value}"])
            else:
                args.extend(["--raw-field", f"{key}={value}"])
        raw = self._run(args, f"{method} {endpoint}")
        return self._json(raw, f"{method} {endpoint}") if json_response else raw

    def repositories(self) -> list[dict[str, Any]]:
        raw = self._run(
            [
                "repo",
                "list",
                self.owner,
                "--limit",
                "1000",
                "--json",
                "name,nameWithOwner,isPrivate,isArchived,description,updatedAt,"
                "stargazerCount,forkCount,primaryLanguage,url,defaultBranchRef,homepageUrl",
            ],
            "chargement des depots",
            timeout=180,
        )
        repos = self._json(raw, "chargement des depots")
        if not isinstance(repos, list):
            raise GitHubError("GitHub n'a pas renvoye une liste de depots.")
        return sorted(repos, key=lambda repo: repo["name"].casefold())

    def repository(self, name: str) -> dict[str, Any]:
        return self._api("GET", f"repos/{self.owner}/{quote(name, safe='')}")

    def create_repository(
        self, name: str, description: str, visibility: str, initialize: bool
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", name):
            raise GitHubError("Le nom du depot contient des caracteres non autorises.")
        if visibility not in {"private", "public"}:
            raise GitHubError("Choisis une visibilite privee ou publique.")
        fields: dict[str, Any] = {
            "name": name,
            "description": description,
            "private": visibility == "private",
            "auto_init": initialize,
        }
        return self._api("POST", "user/repos", fields)

    def update_repository(self, name: str, fields: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "description", "homepage", "visibility"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            raise GitHubError("Aucune modification de depot n'a ete fournie.")
        if updates.get("visibility") not in {None, "private", "public"}:
            raise GitHubError("La visibilite doit etre privee ou publique.")
        if updates.get("name") and not re.fullmatch(
            r"[A-Za-z0-9._-]{1,100}", str(updates["name"])
        ):
            raise GitHubError("Le nom du depot contient des caracteres non autorises.")
        current_name = name
        if updates.get("name") and updates["name"] != name:
            self._api(
                "PATCH",
                f"repos/{self.owner}/{quote(name, safe='')}",
                {"name": updates["name"]},
            )
            current_name = str(updates["name"])
        command = ["repo", "edit", f"{self.owner}/{current_name}"]
        if "description" in updates:
            command.extend(["--description", str(updates["description"])])
        if "homepage" in updates:
            command.extend(["--homepage", str(updates["homepage"])])
        if "visibility" in updates:
            command.extend(
                [
                    "--visibility",
                    str(updates["visibility"]),
                    "--accept-visibility-change-consequences",
                ]
            )
        if len(command) > 2:
            self._run(command, f"modification de {current_name}")
        return self.repository(current_name)

    def set_archived(self, name: str, archived: bool) -> dict[str, Any]:
        command = "archive" if archived else "unarchive"
        self._run(["repo", command, f"{self.owner}/{name}", "--yes"], f"{command} de {name}")
        return self.repository(name)

    def delete_repository(self, name: str) -> None:
        self._api(
            "DELETE",
            f"repos/{self.owner}/{quote(name, safe='')}",
            json_response=False,
        )

    def ensure_private_archive(self, name: str) -> dict[str, Any]:
        try:
            archive = self.repository(name)
        except GitHubError as error:
            if "404" not in str(error):
                raise
            return self.create_repository(
                name,
                "Archive privee des projets GitHub",
                "private",
                initialize=True,
            )
        if archive.get("private") is not True:
            raise GitHubError(
                f"Le depot d'archive {name} existe mais n'est pas prive."
            )
        return archive

    def branches(self, repo: str) -> list[dict[str, Any]]:
        result = self._api(
            "GET",
            f"repos/{self.owner}/{quote(repo, safe='')}/branches?per_page=100",
        )
        if not isinstance(result, list):
            raise GitHubError("GitHub n'a pas renvoye une liste de branches.")
        return result

    def create_branch(self, repo: str, name: str, source: str) -> dict[str, Any]:
        repository = self.repository(repo)
        branch_name = source or repository.get("default_branch")
        if not branch_name:
            raise GitHubError("Le depot n'a pas de branche source par defaut.")
        source_ref = self._api(
            "GET",
            f"repos/{self.owner}/{quote(repo, safe='')}/git/ref/heads/{quote(branch_name, safe='/')}",
        )
        sha = source_ref.get("object", {}).get("sha")
        if not sha:
            raise GitHubError(f"Impossible de trouver la branche source {branch_name}.")
        return self._api(
            "POST",
            f"repos/{self.owner}/{quote(repo, safe='')}/git/refs",
            {"ref": f"refs/heads/{name}", "sha": sha},
        )

    def rename_branch(self, repo: str, old_name: str, new_name: str) -> dict[str, Any]:
        return self._api(
            "POST",
            f"repos/{self.owner}/{quote(repo, safe='')}/branches/"
            f"{quote(old_name, safe='/')}/rename",
            {"new_name": new_name},
        )

    def delete_branch(self, repo: str, name: str) -> None:
        metadata = self.repository(repo)
        if metadata.get("default_branch") == name:
            raise GitHubError("La branche par defaut ne peut pas etre supprimee.")
        branch = next(
            (item for item in self.branches(repo) if item.get("name") == name),
            None,
        )
        if branch is None:
            raise GitHubError(f"La branche {name} n'existe plus.")
        if branch.get("protected"):
            raise GitHubError(
                f"La branche {name} est protegee et ne peut pas etre supprimee ici."
            )
        self._api(
            "DELETE",
            f"repos/{self.owner}/{quote(repo, safe='')}/git/refs/"
            f"heads/{quote(name, safe='/')}",
            json_response=False,
        )

    def pull_requests(self, repo: str) -> list[dict[str, Any]]:
        raw = self._run(
            [
                "pr",
                "list",
                "--repo",
                f"{self.owner}/{repo}",
                "--state",
                "all",
                "--limit",
                "100",
                "--json",
                "number,title,state,author,baseRefName,headRefName,isDraft,"
                "mergeable,mergeStateStatus,reviewDecision,url,createdAt",
            ],
            f"chargement des pull requests de {repo}",
        )
        result = self._json(raw, "chargement des pull requests")
        if not isinstance(result, list):
            raise GitHubError("GitHub n'a pas renvoye une liste de pull requests.")
        return result

    def create_pull_request(
        self, repo: str, title: str, body: str, head: str, base: str, draft: bool
    ) -> dict[str, Any]:
        return self._api(
            "POST",
            f"repos/{self.owner}/{quote(repo, safe='')}/pulls",
            {"title": title, "body": body, "head": head, "base": base, "draft": draft},
        )

    def close_pull_request(self, repo: str, number: int) -> dict[str, Any]:
        return self._api(
            "PATCH",
            f"repos/{self.owner}/{quote(repo, safe='')}/pulls/{number}",
            {"state": "closed"},
        )

    def merge_pull_request(self, repo: str, number: int, method: str) -> dict[str, Any]:
        if method not in {"merge", "squash", "rebase"}:
            raise GitHubError("Methode de fusion non reconnue.")
        pulls = self.pull_requests(repo)
        pull = next((item for item in pulls if item["number"] == number), None)
        if pull is None or pull.get("state") != "OPEN":
            raise GitHubError("Cette pull request n'est pas ouverte.")
        eligible = (
            pull.get("mergeable") == "MERGEABLE"
            and pull.get("mergeStateStatus") == "CLEAN"
            and not pull.get("isDraft")
            and pull.get("reviewDecision") != "REVIEW_REQUIRED"
        )
        if not eligible:
            raise GitHubError(
                "GitHub ne signale pas cette PR comme fusionnable sans blocage. "
                "Verifie les conflits, validations et approbations dans GitHub."
            )
        return self._api(
            "PUT",
            f"repos/{self.owner}/{quote(repo, safe='')}/pulls/{number}/merge",
            {"merge_method": method},
        )

    def issues(self, repo: str) -> list[dict[str, Any]]:
        result = self._api(
            "GET",
            f"repos/{self.owner}/{quote(repo, safe='')}/issues?state=all&per_page=100",
        )
        if not isinstance(result, list):
            raise GitHubError("GitHub n'a pas renvoye une liste d'issues.")
        return [item for item in result if "pull_request" not in item]

    def create_issue(self, repo: str, title: str, body: str) -> dict[str, Any]:
        return self._api(
            "POST",
            f"repos/{self.owner}/{quote(repo, safe='')}/issues",
            {"title": title, "body": body},
        )

    def update_issue(
        self, repo: str, number: int, title: str, body: str, state: str
    ) -> dict[str, Any]:
        if state not in {"open", "closed"}:
            raise GitHubError("Etat d'issue non reconnu.")
        return self._api(
            "PATCH",
            f"repos/{self.owner}/{quote(repo, safe='')}/issues/{number}",
            {"title": title, "body": body, "state": state},
        )

    def workflows(self, repo: str) -> list[dict[str, Any]]:
        result = self._api(
            "GET",
            f"repos/{self.owner}/{quote(repo, safe='')}/actions/workflows?per_page=100",
        )
        return result.get("workflows", [])

    def workflow_runs(self, repo: str) -> list[dict[str, Any]]:
        result = self._api(
            "GET",
            f"repos/{self.owner}/{quote(repo, safe='')}/actions/runs?per_page=30",
        )
        return result.get("workflow_runs", [])

    def rerun_workflow(self, repo: str, run_id: int) -> None:
        self._api(
            "POST",
            f"repos/{self.owner}/{quote(repo, safe='')}/actions/runs/{run_id}/rerun",
            json_response=False,
        )

    def cancel_workflow(self, repo: str, run_id: int) -> None:
        self._api(
            "POST",
            f"repos/{self.owner}/{quote(repo, safe='')}/actions/runs/{run_id}/cancel",
            json_response=False,
        )

    def stats(self) -> dict[str, Any]:
        repos = self.repositories()
        languages: dict[str, int] = {}
        for repo in repos:
            language = (repo.get("primaryLanguage") or {}).get("name") or "Autre"
            languages[language] = languages.get(language, 0) + 1
        return {
            "repositories": len(repos),
            "private": sum(bool(repo.get("isPrivate")) for repo in repos),
            "public": sum(not bool(repo.get("isPrivate")) for repo in repos),
            "archived": sum(bool(repo.get("isArchived")) for repo in repos),
            "stars": sum(int(repo.get("stargazerCount") or 0) for repo in repos),
            "forks": sum(int(repo.get("forkCount") or 0) for repo in repos),
            "languages": sorted(
                ({"name": name, "count": count} for name, count in languages.items()),
                key=lambda item: (-item["count"], item["name"].casefold()),
            ),
        }

    @staticmethod
    def open_external(url: str) -> bool:
        if not url.startswith("https://github.com/"):
            raise GitHubError("Seuls les liens HTTPS GitHub peuvent etre ouverts.")
        return webbrowser.open(url)

    def archive_snapshot(self, repo: str, archive_name: str) -> str:
        if repo.casefold() == archive_name.casefold():
            raise GitHubError("Le depot d'archive ne peut pas etre sa propre source.")
        self.ensure_private_archive(archive_name)

        with tempfile.TemporaryDirectory(prefix="github-archive-") as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "archive"
            self._run(
                ["repo", "clone", f"{self.owner}/{repo}", str(source), "--", "--depth", "1"],
                f"telechargement de {repo}",
                timeout=600,
            )
            commit = self._git(
                ["rev-parse", "HEAD"], "lecture de la revision", cwd=source
            )
            git_dir = source / ".git"
            if git_dir.is_dir():
                shutil.rmtree(git_dir)
            self._run(
                ["repo", "clone", f"{self.owner}/{archive_name}", str(destination)],
                f"telechargement de l'archive",
                timeout=600,
            )
            target = destination / "projets" / quote(repo, safe="") / commit
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, target)
            index = destination / "ARCHIVE-INDEX.md"
            entry = (
                f"- [{repo}](https://github.com/{self.owner}/{repo}) "
                f"— `{commit}` — `projets/{quote(repo, safe='')}/{commit}`"
            )
            existing = index.read_text(encoding="utf-8") if index.exists() else ""
            if entry not in existing:
                with index.open("a", encoding="utf-8") as file:
                    if not existing:
                        file.write(f"# Archive GitHub de {self.owner}\n")
                    file.write(f"\n{entry}\n")
            self._git(["add", "--", "."], "preparation de l'archive", cwd=destination)
            status = self._git(
                ["status", "--porcelain"], "verification des changements", cwd=destination
            )
            if status:
                user = self._json(
                    self._run(["api", "user"], "lecture de l'identite GitHub"),
                    "lecture de l'identite GitHub",
                )
                user_name = user.get("name") or user.get("login")
                email = user.get("email") or (
                    f"{user['id']}+{user['login']}@users.noreply.github.com"
                )
                self._git(
                    ["config", "--local", "user.name", user_name],
                    "configuration de l'auteur local",
                    cwd=destination,
                )
                self._git(
                    ["config", "--local", "user.email", email],
                    "configuration de l'adresse locale",
                    cwd=destination,
                )
                self._git(
                    ["commit", "-m", f"Archive {repo} ({commit[:12]})"],
                    "creation du commit",
                    cwd=destination,
                )
                self._git(
                    ["push", "origin", "HEAD"],
                    "publication de l'archive",
                    cwd=destination,
                    timeout=600,
                )
        return commit
