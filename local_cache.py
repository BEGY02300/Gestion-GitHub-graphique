from __future__ import annotations

import base64
from contextlib import contextmanager
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from platform_paths import app_data_dir


class LocalCache:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            path = app_data_dir() / "cache.sqlite3"
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    owner TEXT PRIMARY KEY COLLATE NOCASE,
                    data TEXT NOT NULL,
                    avatar_mime TEXT,
                    avatar_data BLOB,
                    cached_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS repositories (
                    owner TEXT NOT NULL COLLATE NOCASE,
                    name TEXT NOT NULL COLLATE NOCASE,
                    data TEXT NOT NULL,
                    PRIMARY KEY (owner, name)
                );
                CREATE TABLE IF NOT EXISTS resources (
                    cache_key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def load_snapshot(self) -> dict[str, Any] | None:
        with self._connection() as connection:
            profile = connection.execute(
                "SELECT owner, data, avatar_mime, avatar_data, cached_at "
                "FROM profiles ORDER BY cached_at DESC LIMIT 1"
            ).fetchone()
            if profile is None:
                return None
            repositories = connection.execute(
                "SELECT data FROM repositories WHERE owner = ? COLLATE NOCASE "
                "ORDER BY name COLLATE NOCASE",
                (profile["owner"],),
            ).fetchall()
        profile_data = json.loads(profile["data"])
        avatar_data = profile["avatar_data"]
        avatar_mime = profile["avatar_mime"]
        if avatar_data and avatar_mime:
            encoded = base64.b64encode(avatar_data).decode("ascii")
            profile_data["avatarDataUrl"] = f"data:{avatar_mime};base64,{encoded}"
        else:
            profile_data["avatarDataUrl"] = ""
        return {
            "owner": profile["owner"],
            "profile": profile_data,
            "repositories": [json.loads(row["data"]) for row in repositories],
            "cached_at": profile["cached_at"],
        }

    def save_snapshot(
        self,
        profile: dict[str, Any],
        repositories: list[dict[str, Any]],
        *,
        synchronized: bool = True,
    ) -> dict[str, Any]:
        owner = str(profile.get("login") or "").strip()
        if not owner:
            raise ValueError("Le profil GitHub ne contient pas de nom de compte.")
        stored_profile = {
            key: value
            for key, value in profile.items()
            if key not in {"avatarDataUrl", "avatar_data"}
        }
        avatar_data = profile.get("avatar_data")
        if avatar_data is not None and not isinstance(avatar_data, bytes):
            raise ValueError("Les données locales de l’avatar sont invalides.")
        timestamp = self._now()
        if not synchronized:
            with self._connection() as connection:
                previous_profile = connection.execute(
                    "SELECT cached_at FROM profiles WHERE owner = ? COLLATE NOCASE",
                    (owner,),
                ).fetchone()
            if previous_profile is not None:
                timestamp = previous_profile["cached_at"]
        changed: list[str] = []
        present: set[str] = set()
        with self._connection() as connection:
            for repository in repositories:
                name = str(repository.get("name") or "").strip()
                if not name:
                    continue
                present.add(name.casefold())
                data = self._encode(repository)
                previous = connection.execute(
                    "SELECT data FROM repositories WHERE owner = ? COLLATE NOCASE "
                    "AND name = ? COLLATE NOCASE",
                    (owner, name),
                ).fetchone()
                if previous is None or previous["data"] != data:
                    changed.append(name)
                    connection.execute(
                        """
                        INSERT INTO repositories(owner, name, data)
                        VALUES (?, ?, ?)
                        ON CONFLICT(owner, name) DO UPDATE SET data = excluded.data
                        """,
                        (owner, name, data),
                    )
            previous_names = connection.execute(
                "SELECT name FROM repositories WHERE owner = ? COLLATE NOCASE",
                (owner,),
            ).fetchall()
            removed = [
                row["name"]
                for row in previous_names
                if row["name"].casefold() not in present
            ]
            for name in removed:
                connection.execute(
                    "DELETE FROM repositories WHERE owner = ? COLLATE NOCASE "
                    "AND name = ? COLLATE NOCASE",
                    (owner, name),
                )
            connection.execute(
                """
                INSERT INTO profiles(owner, data, avatar_mime, avatar_data, cached_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(owner) DO UPDATE SET
                    data = excluded.data,
                    avatar_mime = COALESCE(excluded.avatar_mime, profiles.avatar_mime),
                    avatar_data = COALESCE(excluded.avatar_data, profiles.avatar_data),
                    cached_at = excluded.cached_at
                """,
                (
                    owner,
                    self._encode(stored_profile),
                    profile.get("avatar_mime"),
                    avatar_data,
                    timestamp,
                ),
            )
        return {
            "owner": owner,
            "cached_at": timestamp,
            "changed": sorted(changed, key=str.casefold),
            "removed": sorted(removed, key=str.casefold),
        }

    def update_avatar(
        self, owner: str, avatar_url: str, mime_type: str, data: bytes
    ) -> None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT data FROM profiles WHERE owner = ? COLLATE NOCASE",
                (owner,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Aucun profil local en cache pour {owner}.")
            profile = json.loads(row["data"])
            profile["avatarUrl"] = avatar_url
            connection.execute(
                """
                UPDATE profiles
                SET data = ?, avatar_mime = ?, avatar_data = ?, cached_at = ?
                WHERE owner = ? COLLATE NOCASE
                """,
                (self._encode(profile), mime_type, data, self._now(), owner),
            )

    def get_resource(self, cache_key: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT data, cached_at FROM resources WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return {"data": json.loads(row["data"]), "cached_at": row["cached_at"]}

    def set_resource(self, cache_key: str, data: Any) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO resources(cache_key, data, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    data = excluded.data, cached_at = excluded.cached_at
                """,
                (cache_key, self._encode(data), self._now()),
            )

    def delete_resources(self, prefix: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM resources WHERE cache_key LIKE ?",
                (f"{prefix}%",),
            )
