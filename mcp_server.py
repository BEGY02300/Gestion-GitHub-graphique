from __future__ import annotations

import json
import sys
from typing import Any

from github_api import GitHub, GitHubError


PROTOCOL_VERSION = "2025-03-26"
_github: GitHub | None = None


def _client() -> GitHub:
    global _github
    if _github is None:
        _github = GitHub()
    return _github


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "github_list_repositories",
            "description": "Liste les depots GitHub accessibles au compte connecte.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "github_repository_details",
            "description": "Lit les details d'un depot GitHub accessible.",
            "inputSchema": {
                "type": "object",
                "properties": {"repository": {"type": "string"}},
                "required": ["repository"],
                "additionalProperties": False,
            },
        },
        {
            "name": "github_repository_stats",
            "description": "Calcule les statistiques des depots du compte connecte.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "github_list_branches",
            "description": "Liste les branches d'un depot.",
            "inputSchema": {
                "type": "object",
                "properties": {"repository": {"type": "string"}},
                "required": ["repository"],
                "additionalProperties": False,
            },
        },
        {
            "name": "github_list_issues",
            "description": "Liste les issues (sans les pull requests) d'un depot.",
            "inputSchema": {
                "type": "object",
                "properties": {"repository": {"type": "string"}},
                "required": ["repository"],
                "additionalProperties": False,
            },
        },
        {
            "name": "github_list_pull_requests",
            "description": "Liste les pull requests d'un depot.",
            "inputSchema": {
                "type": "object",
                "properties": {"repository": {"type": "string"}},
                "required": ["repository"],
                "additionalProperties": False,
            },
        },
        {
            "name": "github_list_workflows",
            "description": "Liste les workflows GitHub Actions d'un depot.",
            "inputSchema": {
                "type": "object",
                "properties": {"repository": {"type": "string"}},
                "required": ["repository"],
                "additionalProperties": False,
            },
        },
    ]


def _call_tool(name: str, arguments: Any) -> Any:
    if not isinstance(arguments, dict):
        raise ValueError("Les arguments de l'outil doivent etre un objet JSON.")
    if name == "github_list_repositories" and not arguments:
        return _client().repositories()
    if name == "github_repository_stats" and not arguments:
        return _client().stats()
    if name in {"github_list_repositories", "github_repository_stats"}:
        raise ValueError(f"L'outil {name} n'accepte aucun argument.")
    if set(arguments) != {"repository"}:
        raise ValueError("Seul l'argument repository est accepte.")
    repository = arguments.get("repository")
    if not isinstance(repository, str) or not repository.strip():
        raise ValueError("Le nom du depot est obligatoire.")
    github = _client()
    if name == "github_repository_details":
        return github.repository(repository)
    if name == "github_list_branches":
        return github.branches(repository)
    if name == "github_list_issues":
        return github.issues(repository)
    if name == "github_list_pull_requests":
        return github.pull_requests(repository)
    if name == "github_list_workflows":
        return github.workflows(repository)
    raise ValueError(f"Outil MCP inconnu : {name}.")


def _response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Requete JSON-RPC invalide."}}
    method = message.get("method")
    if not isinstance(method, str):
        return {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32600, "message": "Methode manquante."}}
    if "id" not in message:
        return None
    request_id = message["id"]
    params = message.get("params", {})
    if not isinstance(params, dict):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32602, "message": "Parametres JSON-RPC invalides."},
        }
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = (
            requested
            if isinstance(requested, str)
            and requested in {"2024-11-05", PROTOCOL_VERSION}
            else PROTOCOL_VERSION
        )
        return _response(
            request_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "github-desk", "version": "1.0.0"},
            },
        )
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": _tools()})
    if method == "tools/call":
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "Parametres d'outil invalides."}}
        try:
            data = _call_tool(params["name"], params.get("arguments", {}))
        except (GitHubError, ValueError, TypeError) as error:
            return _response(
                request_id,
                {"isError": True, "content": [{"type": "text", "text": str(error)}]},
            )
        text = json.dumps(data, ensure_ascii=False)
        return _response(
            request_id,
            {
                "content": [{"type": "text", "text": text}],
                "structuredContent": {"result": data},
            },
        )
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Methode inconnue : {method}."},
    }


def main() -> int:
    for line in sys.stdin:
        try:
            message = json.loads(line)
            response = handle_message(message)
        except json.JSONDecodeError as error:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"JSON invalide : {error}"},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
