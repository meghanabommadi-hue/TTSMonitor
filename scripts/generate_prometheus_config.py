#!/usr/bin/env python3
"""
Populate prometheus/prometheus.yml with a list of GPU IP addresses.

Usage:
    python generate_prometheus_config.py --ips 1.2.3.4 1.2.3.5 1.2.3.6
    python generate_prometheus_config.py --file ips.txt
    python generate_prometheus_config.py --file ips.txt --port 8764 --output prometheus/prometheus.yml
"""

import argparse
import sys
from pathlib import Path

TEMPLATE = """\
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: "gpu-cluster"

scrape_configs:
  - job_name: "gpu_metrics"
    metrics_path: /metrics
    scrape_interval: 15s
    scrape_timeout: 10s
    static_configs:
      - targets:
{targets}
        labels:
          group: "gpu_cluster"
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Generate Prometheus scrape config from GPU IP list.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ips", nargs="+", metavar="IP", help="Space-separated list of IP addresses")
    source.add_argument("--file", metavar="FILE", help="Text file with one IP per line")
    parser.add_argument("--port", default="8764", help="Metrics port (default: 8764)")
    parser.add_argument("--output", default="prometheus/prometheus.yml", help="Output file path")
    return parser.parse_args()


def load_ips_from_file(path: str) -> list[str]:
    lines = Path(path).read_text().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def main():
    args = parse_args()

    if args.file:
        ips = load_ips_from_file(args.file)
    else:
        ips = args.ips

    if not ips:
        print("Error: no IP addresses provided.", file=sys.stderr)
        sys.exit(1)

    targets = "\n".join(f'          - "{ip}:{args.port}"' for ip in ips)
    config = TEMPLATE.format(targets=targets)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(config)

    print(f"Written {len(ips)} targets to {output_path}")
    for ip in ips:
        print(f"  {ip}:{args.port}")


if __name__ == "__main__":
    main()
