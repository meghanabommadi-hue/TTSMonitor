#!/usr/bin/env python3
"""
Local proxy server for TTS GPU Monitor dashboard.
Fetches metrics from GPU nodes server-side (bypasses browser CORS).

Usage:
    python3 server.py
Then open: http://localhost:8080
"""

import asyncio
from aiohttp import web, ClientSession, ClientTimeout

METRICS_PORT = 8764
METRICS_PATH = "/metrics"
SERVE_PORT   = 8080


async def proxy_metrics(request: web.Request) -> web.Response:
    host = request.query.get("host")
    if not host:
        return web.Response(status=400, text="Missing ?host= param")

    url = f"http://{host}:{METRICS_PORT}{METRICS_PATH}"
    try:
        timeout = ClientTimeout(total=5)
        async with ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                text = await resp.text()
                return web.Response(
                    text=text,
                    content_type="text/plain",
                    headers={"Access-Control-Allow-Origin": "*"},
                )
    except Exception as e:
        return web.Response(
            status=502,
            text=str(e),
            headers={"Access-Control-Allow-Origin": "*"},
        )


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse("dashboard.html")


app = web.Application()
app.router.add_get("/proxy", proxy_metrics)  # must be before static
app.router.add_get("/", index)
app.router.add_static("/", ".")

if __name__ == "__main__":
    print(f"Dashboard running at http://localhost:{SERVE_PORT}")
    web.run_app(app, port=SERVE_PORT, print=None)
