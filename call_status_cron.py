import requests
import os
import json
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ───────────────────────────────────────────
# CONFIG
# ───────────────────────────────────────────
WEBHOOK_URL  = "https://chat.googleapis.com/v1/spaces/AAQADTwcOSU/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=pczlLxcETgIpfoNZevPwyH59ft4Y7YU4SJ5Xmm2h4QQ"
PROXY_BASE   = "http://localhost:8080/proxy"
VACANCY_URL  = "https://ml-xpert-voice.infra.kapturecrm.com/voice/bajaj/client/vacancy/get/1006978"
IPS_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ips.txt")
SCRIPT_PATH  = os.path.abspath(__file__)
PYTHON_PATH  = "/Users/meghana.bommadi/.pyenv/versions/3.8.18/bin/python3"
LOG_PATH     = "/tmp/call_status_cron.log"

# Stop cron after this many consecutive unchanged alerts
MAX_UNCHANGED = 3

# State file to track consecutive unchanged count
STATE_FILE = "/tmp/call_status_cron_state.json"
# ───────────────────────────────────────────

CRON_ENTRY = f"*/5 * * * * {PYTHON_PATH} {SCRIPT_PATH} >> {LOG_PATH} 2>&1"


def load_ips():
    ips = []
    with open(IPS_FILE) as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                ips.append(line)
    return ips


def parse_prometheus(text):
    result = {}
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
        labels = {}
        lb_start = name_labels.find("{")
        if lb_start != -1:
            lb_str = name_labels[lb_start+1:name_labels.rfind("}")]
            for pair in lb_str.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    labels[k.strip()] = v.strip().strip('"')
        result.setdefault(name, []).append({"labels": labels, "value": value})
    return result


def get_val(m, name, filter_fn=None):
    entries = m.get(name, [])
    if filter_fn:
        entries = [e for e in entries if filter_fn(e)]
    return sum(e["value"] for e in entries)


def fetch_node(ip):
    try:
        resp = requests.get(f"{PROXY_BASE}?host={ip}", timeout=5)
        if resp.ok:
            return ip, parse_prometheus(resp.text)
    except Exception:
        pass
    return ip, None


def collect_gpu_stats():
    ips = load_ips()
    node_metrics = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        for ip, m in ex.map(fetch_node, ips):
            if m is not None:
                node_metrics[ip] = m

    named = lambda e: e["labels"].get("voice", "") != ""

    total_ws           = 0
    total_e2e_ms       = 0
    total_e2e_reqs     = 0
    total_cache_hits   = 0
    total_cache_misses = 0

    for m in node_metrics.values():
        total_ws += get_val(m, "tts_active_websockets")

        reqs   = get_val(m, "tts_requests_total", named)
        e2e_ms = get_val(m, "tts_e2e_ms_total",   named)
        if reqs == 0:
            reqs   = get_val(m, "tts_requests_total")
            e2e_ms = get_val(m, "tts_e2e_ms_total")

        total_e2e_ms       += e2e_ms
        total_e2e_reqs     += reqs
        total_cache_hits   += get_val(m, "tts_cache_hits_total")
        total_cache_misses += get_val(m, "tts_cache_misses_total")

    avg_e2e_ms  = (total_e2e_ms / total_e2e_reqs) if total_e2e_reqs > 0 else 0
    avg_e2e_str = f"{avg_e2e_ms/1000:.2f}s" if avg_e2e_ms >= 1000 else (f"{avg_e2e_ms:.0f}ms" if avg_e2e_ms > 0 else "N/A")

    cache_total = total_cache_hits + total_cache_misses
    cache_rate  = f"{(total_cache_hits / cache_total * 100):.1f}%" if cache_total > 0 else "N/A"

    try:
        vr           = requests.get(VACANCY_URL, timeout=5).json()
        active_calls = vr.get("active_calls", "N/A")
        max_calls    = vr.get("max_calls",    "N/A")
        vacant_slots = vr.get("vacant_slots", "N/A")
    except Exception:
        active_calls = max_calls = vacant_slots = "N/A"

    return {
        "up_nodes":     len(node_metrics),
        "total_nodes":  len(ips),
        "active_ws":    int(total_ws),
        "avg_e2e":      avg_e2e_str,
        "cache_rate":   cache_rate,
        "active_calls": active_calls,
        "max_calls":    max_calls,
        "vacant_slots": vacant_slots,
    }


def send_to_gchat(message):
    resp = requests.post(WEBHOOK_URL, json={"text": message})
    resp.raise_for_status()


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"last_key": None, "unchanged_count": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def cron_is_active():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return CRON_ENTRY in result.stdout


def remove_cron():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    new_crontab = "\n".join(
        line for line in result.stdout.splitlines()
        if SCRIPT_PATH not in line
    )
    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    print("Cron removed.")


def add_cron():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout.strip()
    # Remove any old entry for this script first
    lines = [l for l in existing.splitlines() if SCRIPT_PATH not in l]
    lines.append(CRON_ENTRY)
    new_crontab = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    print("Cron added.")


if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Collecting stats...")

    stats = collect_gpu_stats()
    print(json.dumps(stats, indent=2))

    # Build a fingerprint of the key metrics to detect changes
    stat_key = f"{stats['active_calls']}|{stats['active_ws']}|{stats['avg_e2e']}|{stats['cache_rate']}"

    state = load_state()

    if stat_key == state["last_key"]:
        state["unchanged_count"] += 1
    else:
        state["unchanged_count"] = 0

    state["last_key"] = stat_key
    save_state(state)

    if state["unchanged_count"] >= MAX_UNCHANGED:
        # Numbers haven't changed for MAX_UNCHANGED alerts — stop cron
        msg = (
            f"⏸️ TTS Monitor paused — no changes detected for "
            f"{state['unchanged_count']} consecutive alerts. "
            f"Cron stopped. Will restart at 8:30 AM."
        )
        send_to_gchat(msg)
        remove_cron()
        print("Paused: no changes detected.")
    else:
        # Send the normal alert
        ac = f"{stats['active_calls']:,}" if isinstance(stats['active_calls'], int) else stats['active_calls']
        mc = f"{stats['max_calls']:,}"    if isinstance(stats['max_calls'],    int) else stats['max_calls']
        vs = f"{stats['vacant_slots']:,}" if isinstance(stats['vacant_slots'], int) else stats['vacant_slots']

        message = f"""```
📊 TTS GPU Monitor — {timestamp}

📡 Active Calls  : {ac} / {mc}  (vacant: {vs})
🔌 Active WS     : {stats['active_ws']}
⏱️  Avg E2E       : {stats['avg_e2e']}
💾 Cache Hit     : {stats['cache_rate']}
🖥️  Nodes Up      : {stats['up_nodes']} / {stats['total_nodes']}
```"""
        send_to_gchat(message)
        print(f"[{timestamp}] Sent to GChat.")
