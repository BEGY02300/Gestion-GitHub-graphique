from __future__ import annotations

import atexit
import json
import queue
import re
import subprocess
import threading
from typing import Any

from platform_paths import app_data_dir


class MCPError(RuntimeError):
    pass


class MCPServerClient:
    def __init__(self, command: str, args: list[str], timeout: float = 30) -> None:
        if not command.strip():
            raise MCPError("La commande du serveur MCP est obligatoire.")
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise MCPError("Les arguments MCP doivent etre une liste de textes.")
        try:
            self.process = subprocess.Popen(
                [command, *args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as error:
            raise MCPError(f"Impossible de demarrer le serveur MCP : {error}") from error
        self.timeout = timeout
        self._responses: queue.Queue[dict[str, Any] | Exception] = queue.Queue()
        self._write_lock = threading.Lock()
        self._request_id = 0
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()
        try:
            self._request(
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "GitHub Desk", "version": "1.0.0"},
                },
            )
            self._notify("notifications/initialized")
        except MCPError:
            self.close()
            raise

    def _read_output(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError as error:
                self._responses.put(
                    MCPError(f"Reponse JSON invalide du serveur MCP : {error}")
                )
                continue
            if isinstance(message, dict):
                self._responses.put(message)
            else:
                self._responses.put(MCPError("Le serveur MCP a envoye une reponse invalide."))
        if self.process.poll() is not None:
            self._responses.put(
                MCPError(
                    f"Le serveur MCP s'est arrete (code {self.process.returncode})."
                )
            )

    def _send(self, message: dict[str, Any]) -> None:
        if self.process.poll() is not None:
            raise MCPError("Le serveur MCP n'est plus connecte.")
        if self.process.stdin is None:
            raise MCPError("Le canal d'entree du serveur MCP est indisponible.")
        try:
            with self._write_lock:
                self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
        except OSError as error:
            raise MCPError(f"Echec de communication MCP : {error}") from error

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        while True:
            try:
                response = self._responses.get(timeout=self.timeout)
            except queue.Empty as error:
                raise MCPError(f"Delai depasse pour la requete MCP {method}.") from error
            if isinstance(response, Exception):
                raise response
            if response.get("id") != request_id:
                continue
            if "error" in response:
                error = response["error"]
                detail = (
                    error.get("message", "Erreur MCP inconnue.")
                    if isinstance(error, dict)
                    else "Erreur MCP inconnue."
                )
                raise MCPError(str(detail))
            result = response.get("result")
            if not isinstance(result, dict):
                raise MCPError(f"Reponse MCP invalide pour {method}.")
            return result

    def _notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list", {})
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise MCPError("Le serveur MCP n'a pas renvoye de liste d'outils.")
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not name.strip() or not isinstance(arguments, dict):
            raise MCPError("Nom d'outil ou arguments MCP invalides.")
        return self._request(
            "tools/call", {"name": name, "arguments": arguments}
        )

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self._reader.join(timeout=2)
        if self.process.stdin:
            self.process.stdin.close()
        if self.process.stdout and not self._reader.is_alive():
            self.process.stdout.close()


class MCPClientManager:
    def __init__(self) -> None:
        self.config_path = app_data_dir(config=True) / "mcp-servers.json"
        self._clients: dict[str, MCPServerClient] = {}
        self._lock = threading.RLock()
        atexit.register(self.close_all)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.config_path.exists():
            return {}
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MCPError(f"Configuration MCP illisible : {error}") from error
        if not isinstance(data, dict):
            raise MCPError("Le fichier de configuration MCP est invalide.")
        return data

    def _save(self, servers: dict[str, dict[str, Any]]) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.config_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(servers, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            temporary.replace(self.config_path)
        except OSError as error:
            raise MCPError(f"Impossible d'enregistrer la configuration MCP : {error}") from error

    @staticmethod
    def _validate_name(name: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", name):
            raise MCPError(
                "Le nom du serveur doit contenir 1 a 60 lettres, chiffres, points, "
                "tirets ou tirets bas."
            )

    def servers(self) -> list[dict[str, Any]]:
        with self._lock:
            configs = self._load()
            return [
                {
                    "name": name,
                    "command": config.get("command", ""),
                    "args": config.get("args", []),
                    "connected": name in self._clients
                    and self._clients[name].process.poll() is None,
                }
                for name, config in sorted(configs.items())
            ]

    def add_server(self, name: str, command: str, args: list[str]) -> dict[str, Any]:
        self._validate_name(name)
        if not isinstance(command, str) or not command.strip():
            raise MCPError("Indique le chemin du programme du serveur MCP.")
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise MCPError("Les arguments doivent etre fournis sous forme de liste JSON.")
        with self._lock:
            configs = self._load()
            configs[name] = {"command": command.strip(), "args": args}
            self._save(configs)
        return {"name": name, "command": command.strip(), "args": args}

    def remove_server(self, name: str) -> None:
        with self._lock:
            configs = self._load()
            if name not in configs:
                raise MCPError(f"Serveur MCP introuvable : {name}.")
            client = self._clients.pop(name, None)
            if client:
                client.close()
            del configs[name]
            self._save(configs)

    def disconnect(self, name: str) -> None:
        with self._lock:
            client = self._clients.pop(name, None)
            if client:
                client.close()

    def connect(self, name: str) -> list[dict[str, Any]]:
        with self._lock:
            configs = self._load()
            config = configs.get(name)
            if config is None:
                raise MCPError(f"Serveur MCP introuvable : {name}.")
            previous = self._clients.pop(name, None)
            if previous:
                previous.close()
            client = MCPServerClient(config["command"], config["args"])
            self._clients[name] = client
            try:
                return client.list_tools()
            except MCPError:
                self._clients.pop(name, None)
                client.close()
                raise

    def tools(self, name: str) -> list[dict[str, Any]]:
        with self._lock:
            client = self._clients.get(name)
            if client is None:
                raise MCPError(f"Le serveur MCP {name} n'est pas connecte.")
            return client.list_tools()

    def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        with self._lock:
            client = self._clients.get(server_name)
            if client is None:
                raise MCPError(f"Le serveur MCP {server_name} n'est pas connecte.")
            return client.call_tool(tool_name, arguments)

    def close_all(self) -> None:
        with self._lock:
            clients, self._clients = self._clients, {}
        for client in clients.values():
            client.close()
