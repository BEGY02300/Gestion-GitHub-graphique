from __future__ import annotations

from typing import Any, Callable

from github_api import GitHub, GitHubError


class DesktopApi:
    def __init__(self) -> None:
        self.github: GitHub | None = None

    def _invoke(self, operation: Callable[..., Any], *args: Any) -> dict[str, Any]:
        try:
            if self.github is None:
                raise GitHubError("Connecte-toi avec GitHub CLI puis actualise l'application.")
            return {"ok": True, "data": operation(self.github, *args)}
        except GitHubError as error:
            return {"ok": False, "error": str(error)}

    def connect(self) -> dict[str, Any]:
        try:
            self.github = GitHub()
            return {"ok": True, "data": {"owner": self.github.owner}}
        except GitHubError as error:
            return {"ok": False, "error": str(error)}

    def repositories(self) -> dict[str, Any]:
        return self._invoke(lambda github: github.repositories())

    def stats(self) -> dict[str, Any]:
        return self._invoke(lambda github: github.stats())

    def open_external(self, url: str) -> dict[str, Any]:
        def open_link(github: GitHub) -> str:
            if not github.open_external(url):
                raise GitHubError("Le navigateur par defaut n'a pas pu ouvrir ce lien.")
            return "Lien ouvert dans le navigateur."

        return self._invoke(open_link)

    def create_repository(
        self, name: str, description: str, visibility: str, initialize: bool
    ) -> dict[str, Any]:
        return self._invoke(
            lambda github: github.create_repository(name, description, visibility, initialize)
        )

    def update_repository(self, name: str, updates: dict[str, Any]) -> dict[str, Any]:
        return self._invoke(lambda github: github.update_repository(name, updates))

    def set_archived(self, name: str, archived: bool) -> dict[str, Any]:
        return self._invoke(lambda github: github.set_archived(name, archived))

    def delete_repository(self, name: str, confirmation: str) -> dict[str, Any]:
        def delete(github: GitHub) -> str:
            expected = f"SUPPRIMER {github.owner}/{name}"
            if confirmation != expected:
                raise GitHubError("Confirmation incorrecte. Depot non supprime.")
            github.delete_repository(name)
            return f"{github.owner}/{name} supprime."

        return self._invoke(delete)

    def archive_snapshot(self, name: str, archive_name: str) -> dict[str, Any]:
        return self._invoke(lambda github: github.archive_snapshot(name, archive_name))

    def branches(self, repo: str) -> dict[str, Any]:
        return self._invoke(lambda github: github.branches(repo))

    def create_branch(self, repo: str, name: str, source: str) -> dict[str, Any]:
        return self._invoke(lambda github: github.create_branch(repo, name, source))

    def rename_branch(
        self, repo: str, old_name: str, new_name: str
    ) -> dict[str, Any]:
        return self._invoke(lambda github: github.rename_branch(repo, old_name, new_name))

    def delete_branch(
        self, repo: str, name: str, confirmation: str
    ) -> dict[str, Any]:
        def delete(github: GitHub) -> str:
            if confirmation != f"SUPPRIMER {name}":
                raise GitHubError("Confirmation incorrecte. Branche non supprimee.")
            github.delete_branch(repo, name)
            return f"Branche {name} supprimee."

        return self._invoke(delete)

    def pull_requests(self, repo: str) -> dict[str, Any]:
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

        return self._invoke(list_pulls)

    def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool,
    ) -> dict[str, Any]:
        return self._invoke(
            lambda github: github.create_pull_request(
                repo, title, body, head, base, draft
            )
        )

    def close_pull_request(
        self, repo: str, number: int, confirmation: str
    ) -> dict[str, Any]:
        def close(github: GitHub) -> dict[str, Any]:
            if confirmation != f"FERMER PR {number}":
                raise GitHubError("Confirmation incorrecte. Pull request non fermee.")
            return github.close_pull_request(repo, number)

        return self._invoke(close)

    def merge_pull_request(
        self, repo: str, number: int, method: str, confirmation: str
    ) -> dict[str, Any]:
        def merge(github: GitHub) -> dict[str, Any]:
            if confirmation != f"FUSIONNER PR {number}":
                raise GitHubError("Confirmation incorrecte. Pull request non fusionnee.")
            return github.merge_pull_request(repo, number, method)

        return self._invoke(merge)

    def issues(self, repo: str) -> dict[str, Any]:
        return self._invoke(lambda github: github.issues(repo))

    def create_issue(self, repo: str, title: str, body: str) -> dict[str, Any]:
        return self._invoke(lambda github: github.create_issue(repo, title, body))

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

        return self._invoke(update)

    def workflows(self, repo: str) -> dict[str, Any]:
        return self._invoke(lambda github: github.workflows(repo))

    def workflow_runs(self, repo: str) -> dict[str, Any]:
        return self._invoke(lambda github: github.workflow_runs(repo))

    def rerun_workflow(
        self, repo: str, run_id: int, confirmation: str
    ) -> dict[str, Any]:
        def rerun(github: GitHub) -> str:
            if confirmation != f"RELANCER {run_id}":
                raise GitHubError("Confirmation incorrecte. Workflow non relance.")
            github.rerun_workflow(repo, run_id)
            return f"Execution {run_id} relancee."

        return self._invoke(rerun)

    def cancel_workflow(
        self, repo: str, run_id: int, confirmation: str
    ) -> dict[str, Any]:
        def cancel(github: GitHub) -> str:
            if confirmation != f"ANNULER {run_id}":
                raise GitHubError("Confirmation incorrecte. Workflow non annule.")
            github.cancel_workflow(repo, run_id)
            return f"Execution {run_id} annulee."

        return self._invoke(cancel)
