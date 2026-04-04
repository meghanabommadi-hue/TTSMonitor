# GPU Monitor — Commands Reference

## 1. Add GPU IPs

<!-- update and run -->
```bash
./update_nodes.sh ips_new.txt && python3 server.py ips_new.txt
```

**From a file** (`ips.txt` — one IP per line, `#` for comments):
```bash
python generate_prometheus_config.py --file ips.txt
```

**Inline:**
```bash
python generate_prometheus_config.py --ips 34.126.91.108 34.126.91.109 34.126.91.110
```

**Shell script alternative:**
```bash
./update_ips.sh ips.txt
```

---

## 2. Start the stack

```bash
docker compose up -d
```

| Service    | URL                        | Credentials     |
|------------|----------------------------|-----------------|
| Grafana    | http://localhost:3000       | admin / admin   |
| Prometheus | http://localhost:9090       | —               |

---

## 3. Stop the stack

```bash
docker compose down
```

Stop and delete all stored metrics data:
```bash
docker compose down -v
```

---

## 4. Reload Prometheus config (without restart)

Use this after updating `prometheus/prometheus.yml`:
```bash
curl -X POST http://localhost:9090/-/reload
```

---

## 5. View logs

```bash
docker compose logs -f prometheus
docker compose logs -f grafana
```

---

## 6. Check which nodes are UP/DOWN

```bash
curl -s http://localhost:9090/api/v1/query?query=up\{job=\"gpu_metrics\"\} | python -m json.tool
```

Or open Prometheus in the browser and run:
```
up{job="gpu_metrics"}
```

---

## 7. Explore raw metrics from a node

```bash
curl http://<GPU_IP>:8764/metrics
```

---

## 8. Restart a single service

```bash
docker compose restart prometheus
docker compose restart grafana
```

---

## 9. Upgrade images

```bash
docker compose pull
docker compose up -d
```

---

## File reference

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Defines Prometheus + Grafana services |
| `prometheus/prometheus.yml` | Scrape targets (GPU IPs live here) |
| `generate_prometheus_config.py` | Populates `prometheus.yml` from an IP list |
| `update_ips.sh` | Shell alternative to the Python script |
| `grafana/dashboards/gpu_cluster.json` | Pre-built Grafana dashboard |
| `grafana/provisioning/` | Auto-wires datasource + dashboard on startup |
