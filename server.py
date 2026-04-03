#!/usr/bin/env python3
"""
Local proxy server for TTS GPU Monitor dashboard.
- Serves dashboard.html and node.html
- Proxies /metrics requests to GPU nodes (bypasses browser CORS)
- Scrapes all nodes every 15s and stores snapshots in an in-memory cache
- Exposes /history?host=<ip>&since=<unix_ms> for time-range queries

Usage:
    python3 server.py
Then open: http://localhost:8080
"""

import asyncio
import time
import json
from collections import defaultdict, deque
from aiohttp import web, ClientSession, ClientTimeout

METRICS_PORT = 8764
METRICS_PATH = "/metrics"
SERVE_PORT   = 8080
SCRAPE_INTERVAL_S = 15
MAX_SNAPSHOTS     = 1440  # ~6 hours at 15s interval per node

# IPs loaded from ips.txt at startup
NODES: list[str] = []

# cache[ip] = deque of {"ts": unix_ms, "metrics": {name: [{labels, value}]}}
cache: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_SNAPSHOTS))


# ── Prometheus parser ────────────────────────────────────────────────────────

def parse_prometheus(text: str) -> dict:
    result: dict[str, list] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        name_labels, value_str = parts
        try:
            value = float(value_str)
        except ValueError:
            continue
        name = name_labels.split("{")[0]
        labels: dict[str, str] = {}
        lb_start = name_labels.find("{")
        if lb_start != -1:
            lb_str = name_labels[lb_start + 1:name_labels.rfind("}")]
            for pair in lb_str.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    labels[k.strip()] = v.strip().strip('"')
        if name not in result:
            result[name] = []
        result[name].append({"labels": labels, "value": value})
    return result


# ── Background scraper ───────────────────────────────────────────────────────

async def scrape_node(session: ClientSession, ip: str):
    url = f"http://{ip}:{METRICS_PORT}{METRICS_PATH}"
    try:
        async with session.get(url, timeout=ClientTimeout(total=5)) as resp:
            text = await resp.text()
            snapshot = {
                "ts": int(time.time() * 1000),
                "metrics": parse_prometheus(text),
            }
            cache[ip].append(snapshot)
    except Exception:
        pass  # node unreachable — just skip this tick


async def scrape_loop():
    while True:
        async with ClientSession() as session:
            await asyncio.gather(*[scrape_node(session, ip) for ip in NODES])
        await asyncio.sleep(SCRAPE_INTERVAL_S)


# ── HTTP handlers ────────────────────────────────────────────────────────────

async def handle_proxy(request: web.Request) -> web.Response:
    """Proxy a single /metrics fetch (used by dashboard on-demand)."""
    host = request.query.get("host")
    if not host:
        return web.Response(status=400, text="Missing ?host=")
    url = f"http://{host}:{METRICS_PORT}{METRICS_PATH}"
    try:
        async with ClientSession() as session:
            async with session.get(url, timeout=ClientTimeout(total=5)) as resp:
                text = await resp.text()
                return web.Response(text=text, content_type="text/plain",
                                    headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        return web.Response(status=502, text=str(e),
                            headers={"Access-Control-Allow-Origin": "*"})


async def handle_history(request: web.Request) -> web.Response:
    """
    Return cached snapshots for a node, optionally filtered by time.

    Query params:
      host=<ip>           required
      since=<unix_ms>     optional — only return snapshots after this timestamp
      last=<N>            optional — return only the last N snapshots
    """
    host = request.query.get("host")
    if not host:
        return web.Response(status=400, text="Missing ?host=")

    since   = int(request.query.get("since", 0))
    last_n  = int(request.query.get("last", 0))

    snapshots = list(cache.get(host, []))

    if since:
        snapshots = [s for s in snapshots if s["ts"] >= since]
    if last_n:
        snapshots = snapshots[-last_n:]

    return web.Response(
        text=json.dumps(snapshots),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def handle_cache_info(request: web.Request) -> web.Response:
    """Return how many snapshots are cached per node."""
    info = {ip: len(cache[ip]) for ip in NODES}
    oldest = {}
    for ip in NODES:
        if cache[ip]:
            oldest[ip] = cache[ip][0]["ts"]
    return web.Response(
        text=json.dumps({"snapshots": info, "oldest_ts": oldest, "max": MAX_SNAPSHOTS}),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def handle_index(request: web.Request) -> web.FileResponse:
    return web.FileResponse("dashboard.html")


# ── App startup ──────────────────────────────────────────────────────────────

async def on_startup(app):
    # Load IPs
    global NODES
    try:
        with open("ips.txt") as f:
            NODES = [
                line.strip() for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
        print(f"Loaded {len(NODES)} nodes from ips.txt")
    except FileNotFoundError:
        print("ips.txt not found — no background scraping")

    # Start background scraper
    asyncio.create_task(scrape_loop())
    print(f"Scraping every {SCRAPE_INTERVAL_S}s, keeping up to {MAX_SNAPSHOTS} snapshots per node (~{MAX_SNAPSHOTS * SCRAPE_INTERVAL_S // 3600}h)")


app = web.Application()
app.on_startup.append(on_startup)
app.router.add_get("/proxy",      handle_proxy)
app.router.add_get("/history",    handle_history)
app.router.add_get("/cache-info", handle_cache_info)
app.router.add_get("/",           handle_index)
app.router.add_static("/",        ".")

if __name__ == "__main__":
    print(f"Dashboard at http://localhost:{SERVE_PORT}")
    web.run_app(app, port=SERVE_PORT, print=None)
