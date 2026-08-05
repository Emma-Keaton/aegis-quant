# Prometheus + Grafana Monitoring Plan — Aegis Quant

## Overview

Add observability to track trading performance, system health, and error rates.
Prometheus scrapes metrics from the backend; Grafana visualizes them.

---

## What We'll Monitor

### Trading Metrics
| Metric | Type | Purpose |
|--------|------|---------|
| `trades_executed_total` | Counter | Total trades (by symbol, side, venue) |
| `trade_pnl_total` | Gauge | Realized PnL in USD |
| `active_positions_count` | Gauge | Open positions |
| `win_rate_ratio` | Gauge | Win/Loss ratio |
| `trade_latency_seconds` | Histogram | Order fill time |
| `confidence_scores` | Histogram | AI decision confidence distribution |

### Engine Metrics
| Metric | Type | Purpose |
|--------|------|---------|
| `analysis_cycles_total` | Counter | How many cycles ran |
| `analysis_duration_seconds` | Histogram | Time per analysis |
| `signals_generated_total` | Counter | Signals by type |
| `engine_errors_total` | Counter | Errors by engine |

### Source Metrics (Engine B)
| Metric | Type | Purpose |
|--------|------|---------|
| `sources_scanned_total` | Counter | Sources checked |
| `signals_by_source` | Counter | Signals per source (Twitter, RSS, Telegram) |
| `source_errors_total` | Counter | Failed scrapes |

### System Metrics
| Metric | Type | Purpose |
|--------|------|---------|
| `http_requests_total` | Counter | API request count (auto by FastAPI) |
| `http_request_duration_seconds` | Histogram | API latency (auto by FastAPI) |
| `app_up` | Gauge | Uptime (1 = up) |
| `python_memory_bytes` | Gauge | Process memory |

---

## Implementation Plan

### 1. Backend — Prometheus Client (`backend/app/metrics/`)

```
backend/app/metrics/
├── __init__.py          # Registry + helpers
├── trading.py           # Trade-specific metrics
├── engine.py            # Engine analysis metrics
├── sources.py           # Engine B source metrics
└── system.py            # System/resource metrics
```

**Key file:** `backend/app/metrics/__init__.py`
- Create Prometheus registry
- Expose `/metrics` endpoint
- Add FastAPI middleware for auto-tracking

**New endpoint:** `GET /metrics` — Prometheus scrape target

### 2. Docker Compose — Add Prometheus + Grafana

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### 3. Prometheus Config (`monitoring/prometheus.yml`)

```yaml
scrape_configs:
  - job_name: 'aegis-backend'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['backend:8000']
```

### 4. Grafana Dashboards (`monitoring/grafana/dashboards/`)

- **Trading Overview** — PnL, win rate, positions
- **Engine Performance** — Analysis speed, signal quality
- **System Health** — Errors, latency, memory

---

## Files to Create

| File | Purpose |
|------|---------|
| `backend/app/metrics/__init__.py` | Registry + /metrics endpoint |
| `backend/app/metrics/trading.py` | Trade counters/gauges |
| `backend/app/metrics/engine.py` | Engine metrics |
| `backend/app/metrics/sources.py` | Source metrics |
| `monitoring/prometheus.yml` | Prometheus config |
| `monitoring/grafana/dashboards/trading.json` | Trading dashboard |
| `monitoring/grafana/dashboards/engine.json` | Engine dashboard |
| `monitoring/grafana/provisioning/datasources.yml` | Auto-configure Prometheus |

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/main.py` | Register /metrics endpoint |
| `backend/app/api/v1/execute.py` | Instrument trade calls |
| `backend/app/engines/aegis_engine.py` | Instrument analysis cycles |
| `backend/app/engines/engine_b.py` | Instrument source scans |
| `docker-compose.yml` | Add prometheus + grafana services |
| `backend/requirements.txt` | Add `prometheus-client` |

---

## Render Deployment

**Option A — External (Recommended for free tier):**
- Use [Prometheus Dashboard for Render](https://render.com/docs/explore) or Grafana Cloud (free tier)
- Push metrics via pushgateway or direct scrape

**Option B — Self-hosted (Requires paid Render instance):**
- Add Prometheus + Grafana as separate Render services
- More control, but costs money

**Recommendation:** Start with Option A (Grafana Cloud free tier) for production, Docker Compose for local dev.

---

## Local Dev Setup

```bash
# Start everything
docker-compose up -d

# Access panels
http://localhost:9090      # Prometheus
http://localhost:3000      # Grafana (admin/admin)
http://localhost:8000/metrics  # Backend metrics
```

---

## Timeline

| Phase | Work | Time |
|-------|------|------|
| 1 | Create metrics modules + /metrics endpoint | 1-2 hours |
| 2 | Instrument trading engine + execute | 1 hour |
| 3 | Docker Compose + Prometheus config | 30 min |
| 4 | Grafana dashboards | 1 hour |
| 5 | Render setup (optional) | 1 hour |

**Total: ~4-5 hours**

---

## Approval Needed

- [ ] Proceed with local Docker Compose monitoring?
- [ ] Add Grafana Cloud for production (free tier)?
- [ ] Set alerts (e.g., trade failure rate > 10%)?
