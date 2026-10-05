"""The HTTP side of budget-box: what the Kindle talks to.

GET /screen.png?view=&w=&h=&rotate=  the page as a grayscale PNG. X-Data-Version carries the
                                     source's change counter for the next /wait.
GET /wait?v=N&timeout=S              long poll: answers as soon as the data changed since N, or
                                     after S seconds as a heartbeat (so the clock and day stay
                                     honest). The device never polls on a timer.
GET /views                           the page ids to cycle through, one per line (it's read by
                                     a shell script on the device).
GET /status                          the device's last check-in: when, its LAN IP, battery.
GET /healthz                         liveness, no auth.

The device authenticates with DEVICE_TOKEN (Authorization: Bearer ...). It may send X-Kindle-Ip
and X-Kindle-Battery, which are kept so the device can be found again.

Config (env): SOURCE=http|demo, SOURCE_URL + SOURCE_TOKEN for http, DEMO_DIR for demo,
DEVICE_TOKEN, DATA_DIR (where status.json lives), TZ.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from . import render
from .source import DemoSource, HttpSource, Source, UnknownView

ROOT = Path(__file__).resolve().parents[2]


def make_source() -> Source:
    kind = os.environ.get("SOURCE", "demo")
    if kind == "http":
        return HttpSource(os.environ["SOURCE_URL"], os.environ["SOURCE_TOKEN"])
    if kind == "demo":
        return DemoSource(Path(os.environ.get("DEMO_DIR", ROOT / "tests" / "fixtures")))
    raise RuntimeError(f"unknown SOURCE {kind!r}")


app = FastAPI(title="budget-box", docs_url=None, redoc_url=None)
app.state.source = make_source()
DEVICE_TOKEN = os.environ.get("DEVICE_TOKEN", "")
STATUS = Path(os.environ.get("DATA_DIR", "/data")) / "status.json"


def _auth(authorization: str) -> None:
    scheme, _, token = authorization.partition(" ")
    if not DEVICE_TOKEN:
        raise HTTPException(503, "DEVICE_TOKEN is not set")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token.strip(), DEVICE_TOKEN):
        raise HTTPException(401, "bad token")


def _check_in(request: Request, battery: str | None) -> None:
    try:
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(json.dumps({
            "seen_at": datetime.now(render.TZ).isoformat(timespec="seconds"),
            "lan_ip": request.headers.get("x-kindle-ip"), "battery": battery,
            "remote": request.client.host if request.client else None,
        }))
    except OSError:
        pass  # a read-only or missing data dir must never break the screen


@app.exception_handler(httpx.HTTPError)
async def source_unavailable(request: Request, exc: httpx.HTTPError):
    """The data source is down or restarting: a clean 502, so the device backs off and retries
    (it keeps its last image on screen meanwhile)."""
    return JSONResponse({"error": "data source unavailable", "detail": type(exc).__name__}, status_code=502)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/screen.png")
async def screen(request: Request, authorization: str = Header(default=""), view: str = "",
                 w: int = Query(1072, ge=200, le=4000), h: int = Query(1448, ge=200, le=4000),
                 rotate: int = Query(0), x_kindle_battery: str | None = Header(default=None)):
    _auth(authorization)
    if rotate not in (0, 90, 270):
        raise HTTPException(400, "rotate must be 0, 90 or 270")
    src: Source = request.app.state.source
    view = view or (await src.views())[0]
    try:
        page, version = await src.page(view)
    except UnknownView:
        raise HTTPException(404, "unknown view")
    battery = f"{x_kindle_battery.strip().rstrip('%')}%" if x_kindle_battery else None
    _check_in(request, battery)
    png = render.render(page, w, h, battery, rotate)
    return Response(png, media_type="image/png",
                    headers={"Cache-Control": "no-store", "X-Data-Version": str(version)})


@app.get("/wait")
async def wait(request: Request, authorization: str = Header(default=""), v: int = Query(0),
               timeout: float = Query(900, ge=1, le=3600)):
    _auth(authorization)
    version, changed = await request.app.state.source.wait(v, timeout)
    return JSONResponse({"version": version, "changed": changed})


@app.get("/views", response_class=PlainTextResponse)
async def views(request: Request, authorization: str = Header(default="")):
    _auth(authorization)
    return "\n".join(await request.app.state.source.views()) + "\n"


@app.get("/status")
def status(authorization: str = Header(default="")):
    _auth(authorization)
    try:
        return JSONResponse(json.loads(STATUS.read_text()))
    except (OSError, ValueError):
        return JSONResponse({})
