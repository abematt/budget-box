"""Where the numbers come from.

budget-box never touches a database. It asks a *source* for pages as JSON (the contract is in
docs/data-contract.md) and for a change signal it can long-poll. Two sources ship:

- HttpSource: a backend that implements the three endpoints (views, data, wait) over HTTP with a
  bearer token. The author's household ledger is one.
- DemoSource: fixture pages from tests/fixtures, and a change signal that never fires. Lets anyone
  run the whole display stack without a backend.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Protocol

import httpx


class Source(Protocol):
    async def views(self) -> list[str]: ...
    async def page(self, view: str) -> tuple[dict[str, Any], int]: ...   # (data, version)
    async def wait(self, since: int, timeout: float) -> tuple[int, bool]: ...  # (version, changed)


class UnknownView(LookupError):
    pass


class HttpSource:
    """GET {base}/views (one view id per line), {base}/data?view=..., {base}/wait?v=&timeout=."""

    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(20.0))

    async def views(self) -> list[str]:
        r = await self.client.get(f"{self.base}/views", headers=self.headers)
        r.raise_for_status()
        return [line.strip() for line in r.text.splitlines() if line.strip()]

    async def page(self, view: str) -> tuple[dict[str, Any], int]:
        r = await self.client.get(f"{self.base}/data", params={"view": view}, headers=self.headers)
        if r.status_code == 404:
            raise UnknownView(view)
        r.raise_for_status()
        return r.json(), int(r.headers.get("x-ledger-version") or r.headers.get("x-data-version") or 0)

    async def wait(self, since: int, timeout: float) -> tuple[int, bool]:
        r = await self.client.get(f"{self.base}/wait", params={"v": since, "timeout": timeout},
                                  headers=self.headers, timeout=timeout + 30)
        r.raise_for_status()
        j = r.json()
        return int(j["version"]), bool(j.get("changed"))


class DemoSource:
    """Pages from JSON files: <dir>/<view>.json, in name order, view ids taken from file names
    (a "personal-" prefix becomes "personal:")."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.version = int(time.time())

    def _files(self) -> dict[str, Path]:
        out = {}
        for p in sorted(self.folder.glob("*.json")):
            out[p.stem.replace("personal-", "personal:", 1)] = p
        return out

    async def views(self) -> list[str]:
        return list(self._files())

    async def page(self, view: str) -> tuple[dict[str, Any], int]:
        f = self._files().get(view)
        if f is None:
            raise UnknownView(view)
        return json.loads(f.read_text()), self.version

    async def wait(self, since: int, timeout: float) -> tuple[int, bool]:
        if since != self.version:
            return self.version, True
        await asyncio.sleep(timeout)
        return self.version, False
