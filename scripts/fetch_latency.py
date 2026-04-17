#!/usr/bin/env python3
"""
Fetch latency metrics from a TTS GPU node and return a JSON object with:
  - llm_ttft_ms   : avg LLM time-to-first-token (ms)
  - dec_ttft_ms   : avg decoder time-to-first-chunk (ms)
  - total_ms      : avg total E2E latency (ms)
  - source        : "gauge" if new metrics present, "counter_avg" if computed from counters

Usage:
    python3 fetch_latency.py <host:port>
    python3 fetch_latency.py 34.87.172.248:8764
"""

import sys
import json
import urllib.request
import urllib.error
from collections import defaultdict


def fetch_metrics(host: str, timeout: int = 5) -> str:
    url = f"http://{host}/metrics"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def parse_prometheus(text: str) -> dict[str, list[float]]:
    """Parse Prometheus text format into {metric_name: [value, ...]}."""
    result: dict[str, list[float]] = defaultdict(list)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split off the value (last whitespace-separated token)
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        name_labels, value_str = parts
        try:
            value = float(value_str)
        except ValueError:
            continue
        # Strip labels to get bare metric name
        name = name_labels.split("{")[0]
        result[name].append(value)
    return result


def extract_latency(host: str) -> dict:
    raw = fetch_metrics(host)
    m = parse_prometheus(raw)

    # ── Prefer new gauge metrics (available after server restart) ────────────
    if (
        "tts_llm_ttft_avg_ms" in m
        and "tts_dec_ttft_avg_ms" in m
        and "tts_total_avg_ms" in m
    ):
        avg = lambda name: round(sum(m[name]) / len(m[name]), 2)
        return {
            "llm_ttft_ms": avg("tts_llm_ttft_avg_ms"),  # ~27ms
            "dec_ttft_ms": avg("tts_dec_ttft_avg_ms"),  # ~520ms
            "total_ms":    avg("tts_total_avg_ms"),      # ~1045ms
            "source": "gauge",
        }

    # ── Fall back to counter totals ──────────────────────────────────────────
    # NOTE: tts_llm_ms_total is full LLM generation time, NOT TTFT — not computable here.
    # Named voices only — voice="" are warmup/batch calls with anomalously high latency.
    def named_sum(metric: str) -> float:
        total = 0.0
        for line in raw.splitlines():
            if not line.startswith(metric + "{") or 'voice=""' in line:
                continue
            try:
                total += float(line.rsplit(None, 1)[-1])
            except ValueError:
                pass
        return total

    total_requests = named_sum("tts_requests_total")

    if total_requests == 0:
        return {
            "llm_ttft_ms": None,
            "dec_ttft_ms": None,
            "total_ms":    None,
            "source": "counter_avg",
            "error": "no named-voice requests recorded yet",
        }

    return {
        "llm_ttft_ms": None,  # not computable from counters
        "dec_ttft_ms": round(named_sum("tts_decode_ms_total") / total_requests, 2),
        "total_ms":    round(named_sum("tts_e2e_ms_total")    / total_requests, 2),
        "source": "counter_avg",
    }


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "34.87.172.248:8764"
    try:
        result = extract_latency(host)
    except urllib.error.URLError as e:
        result = {"error": str(e), "host": host}
    print(json.dumps(result, indent=2))
