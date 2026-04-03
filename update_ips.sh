#!/usr/bin/env bash
# Usage: ./update_ips.sh ips.txt
# ips.txt should contain one IP per line (without port)
# This script regenerates prometheus/prometheus.yml targets

IPS_FILE="${1:-ips.txt}"

if [ ! -f "$IPS_FILE" ]; then
  echo "Error: $IPS_FILE not found."
  echo "Usage: $0 <path-to-ip-list.txt>"
  exit 1
fi

TARGETS=""
while IFS= read -r ip; do
  # Skip blank lines and comments
  [[ -z "$ip" || "$ip" == \#* ]] && continue
  TARGETS="${TARGETS}          - \"${ip}:8764\"\n"
done < "$IPS_FILE"

cat > prometheus/prometheus.yml <<EOF
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
$(printf "$TARGETS")        labels:
          group: "gpu_cluster"
EOF

echo "Updated prometheus/prometheus.yml with $(grep -c ':8764' prometheus/prometheus.yml) targets."
echo "Reloading Prometheus config..."
curl -s -X POST http://localhost:9090/-/reload && echo "Prometheus reloaded." || echo "Reload failed (is Prometheus running?)"
