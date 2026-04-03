# TTS GPU Monitor

A lightweight real-time dashboard for monitoring a fleet of TTS (Text-to-Speech) GPU inference servers. Scrapes Prometheus metrics directly from each node and displays them in a clean browser UI — no Grafana required.

![Dashboard](https://img.shields.io/badge/stack-Python%20%7C%20aiohttp%20%7C%20Chart.js-blue)
![Nodes](https://img.shields.io/badge/nodes-67%20GPUs-green)

---

## Features

- **Summary panel** — avg active WebSockets, avg TTFT, avg requests, nodes up/down at a glance
- **Per-node WebSocket grid** — all 64 nodes in a compact chip layout, live counts
- **Node cards** — per-node breakdown: requests, errors, latency, WebSocket utilization, per-voice stats
- **Charts tab** — bar and line charts for requests, E2E/LLM/decode latency, WebSockets over time
- **Auto-refresh** every 10 seconds
- **CORS proxy** — fetches metrics server-side, no browser CORS issues

---

## Stack

| Component | Purpose |
|-----------|---------|
| `server.py` | aiohttp server — serves the dashboard + proxies `/metrics` requests |
| `dashboard.html` | Single-file frontend (Chart.js, no build step) |
| `docker-compose.yml` | Optional Prometheus + Grafana stack |
| `prometheus/prometheus.yml` | Prometheus scrape config (all 64 GPU IPs) |
| `generate_prometheus_config.py` | Regenerates Prometheus config from `ips.txt` |

---

## Quick Start

### 1. Install dependencies

```bash
pip install aiohttp
```

### 2. Start the dashboard server

```bash
python3 server.py
```

Open **http://localhost:8080** in your browser.

---

## Managing GPU IPs

All IPs live in `ips.txt` (one per line, `#` for comments).

To update the node list:

```bash
# Edit ips.txt, then regenerate configs:
python3 generate_prometheus_config.py --file ips.txt

# Or pass IPs inline:
python3 generate_prometheus_config.py --ips 1.2.3.4 1.2.3.5
```

Also update the `NODES` array at the top of `dashboard.html` to match.

---

## Optional: Prometheus + Grafana

If you want long-term metric storage and Grafana dashboards:

```bash
docker compose up -d
```

| Service    | URL                   | Credentials   |
|------------|-----------------------|---------------|
| Grafana    | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | —             |

The GPU Cluster Monitor dashboard is pre-loaded in Grafana automatically.

---

## Metrics

Each GPU node exposes a Prometheus endpoint at `:8764/metrics`. Key metrics tracked:

| Metric | Description |
|--------|-------------|
| `tts_requests_total` | Total successful TTS requests (by voice) |
| `tts_e2e_ms_total` | End-to-end latency total (ms) |
| `tts_llm_ms_total` | LLM inference time total (ms) — used as TTFT proxy |
| `tts_decode_ms_total` | Decoder time total (ms) |
| `tts_active_websockets` | Currently active WebSocket connections |
| `tts_open_ports` | Currently open WebSocket ports |
| `tts_errors_total` | Failed TTS requests |
| `tts_short_audio_total` | Suspiciously short audio generations |
| `tts_engine_info` | Engine config (backend, GPU IDs, tensor parallelism) |

---

## File Reference

```
monitor/
├── dashboard.html                        # Browser UI (single file)
├── server.py                             # Local proxy + static server
├── ips.txt                               # One GPU IP per line
├── generate_prometheus_config.py         # Regenerates prometheus.yml from ips.txt
├── update_ips.sh                         # Shell alternative to Python script
├── commands.md                           # Common commands reference
├── docker-compose.yml                    # Prometheus + Grafana stack
├── prometheus/
│   └── prometheus.yml                    # Scrape targets (auto-generated)
└── grafana/
    ├── provisioning/                     # Auto-wires datasource + dashboard
    └── dashboards/gpu_cluster.json       # Pre-built Grafana dashboard
```
