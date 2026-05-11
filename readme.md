# Weather Alert API — Nginx Reverse Proxy & PostgreSQL Performance on Azure

A production-grade infrastructure project demonstrating Nginx reverse proxy configuration, zero-downtime deployments, and PostgreSQL query optimisation across Azure VMs provisioned with Terraform.

---

## Architecture

```
                        Internet
                            │
                    ┌───────▼────────┐
                    │   Nginx VM     │  20.86.167.251
                    │                │  - Reverse proxy
                    │  Rate limiting │  - Load balancing
                    │  Health checks │  - Upstream failover
                    └───────┬────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
    ┌─────────▼──────────┐     ┌──────────▼─────────┐
    │    App VM 1        │     │    App VM 2         │
    │  10.0.1.5:8000     │     │  10.0.1.6:8000      │
    │  FastAPI + Uvicorn │     │  FastAPI + Uvicorn  │
    └─────────┬──────────┘     └────────────────────┘
              │
    ┌─────────▼──────────┐
    │    PostgreSQL       │
    │  weatheralerts DB   │
    │  alert_configs      │
    │  alert_logs (50k)   │
    └────────────────────┘
```

**All infrastructure provisioned with Terraform.**

---

## Stack

| Layer | Technology |
|-------|-----------|
| Cloud | Azure (3x Standard_B1s VMs) |
| IaC | Terraform |
| Reverse Proxy | Nginx |
| Application | Python, FastAPI, Uvicorn |
| Database | PostgreSQL 14 |
| OS | Ubuntu 22.04 LTS |

---

## What This Project Demonstrates

### 1. Nginx as a Reverse Proxy

Nginx sits in front of two upstream app servers and handles:

- **Load balancing** — round-robin distribution across app-vm-1 and app-vm-2
- **Rate limiting** — 10 requests/second per IP with burst allowance of 20
- **Health check timeouts** — 5s connect timeout, 10s read timeout
- **Header forwarding** — `X-Real-IP` and `X-Forwarded-For` passed to upstream

```nginx
upstream weatherapp_backend {
    server 10.0.1.5:8000;
    server 10.0.1.6:8000;
}

server {
    listen 80;
    server_name _;

    location / {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://weatherapp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_connect_timeout 5s;
        proxy_read_timeout 10s;
    }

    location /health {
        proxy_pass http://weatherapp_backend;
        proxy_set_header Host $host;
        access_log off;
    }
}
```

The `limit_req_zone` directive is defined in the `http` block of `nginx.conf` rather than the server block — a common misconfiguration that causes startup failures.

---

### 2. Zero-Downtime Rolling Deployment

Deployments cycle each server out of Nginx rotation before updating, ensuring traffic is never dropped.

**Script logic per server:**
1. Mark server as `down` in Nginx upstream
2. Reload Nginx — traffic shifts entirely to the other server
3. Deploy new code via SSH
4. Run health check against the updated server
5. If healthy — restore to upstream rotation and reload Nginx
6. If unhealthy — keep server out of rotation and exit with error

```bash
deploy_to_server() {
    local SERVER=$1

    # Remove from rotation
    sudo sed -i "s|server $SERVER:8000;|server $SERVER:8000 down;|" $NGINX_CONFIG
    sudo nginx -s reload
    sleep 2

    # Deploy
    ssh -o StrictHostKeyChecking=no -i /home/azureuser/.ssh/id_rsa $APP_USER@$SERVER \
        "cd $APP_DIR && source venv/bin/activate && pip install -q fastapi uvicorn && sudo systemctl restart weatherapp"
    sleep 3

    # Health check
    HEALTH=$(curl -s http://$SERVER:8000/health | grep -o '"healthy"')

    if [ "$HEALTH" == '"healthy"' ]; then
        sudo sed -i "s|server $SERVER:8000 down;|server $SERVER:8000;|" $NGINX_CONFIG
        sudo nginx -s reload
    else
        echo "ERROR: Health check failed — $SERVER kept out of rotation"
        exit 1
    fi
}
```

This approach achieves zero-downtime without Kubernetes or any orchestration tool — using only Nginx upstream configuration and a bash script.

---

### 3. PostgreSQL Query Performance Analysis

The `weatheralerts` database stores alert configurations and a log of triggered alerts. The `alert_logs` table was seeded with **50,000 rows** to simulate production load and expose real query performance issues.

#### Schema

```sql
CREATE TABLE alert_configs (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    condition VARCHAR(50),
    threshold DECIMAL(5,2),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_triggered TIMESTAMP
);

CREATE TABLE alert_logs (
    id SERIAL PRIMARY KEY,
    config_id INTEGER REFERENCES alert_configs(id),
    triggered_at TIMESTAMP DEFAULT NOW(),
    weather_data JSON,
    notification_sent BOOLEAN DEFAULT FALSE
);
```

#### Problem Identified

A `config_id` lookup query was performing a full sequential scan across all 50,000 rows:

```sql
EXPLAIN ANALYZE
SELECT id, triggered_at, weather_data
FROM alert_logs
WHERE config_id = 42
ORDER BY triggered_at DESC;
```

**Before index — Seq Scan:**
```
Seq Scan on alert_logs
  Filter: (config_id = 42)
  Rows Removed by Filter: 49892
Execution Time: 5.317 ms
```

#### Fix Applied

```sql
CREATE INDEX idx_alert_logs_config_id ON alert_logs(config_id);
```

**After index — Bitmap Index Scan:**
```
Bitmap Index Scan on idx_alert_logs_config_id
  Index Cond: (config_id = 42)
Execution Time: 0.489 ms
```

#### Result
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Execution time | 150.444ms | 21.731ms | **86% faster** |
| Scan type | Sequential (50k rows) | Bitmap Index (108 rows) | — |



#### Query Planner Behaviour — An Important Note

For queries with low selectivity (returning ~50% of rows), PostgreSQL's query planner correctly chose sequential scans over index scans even after indexes were created. For example, `WHERE notification_sent = false` matched ~25,000 of 50,000 rows — at that ratio, the cost of reading the index plus fetching rows exceeds the cost of a full table scan.

This is expected and correct behaviour. Indexes provide the greatest benefit on high-selectivity queries — those returning a small percentage of total rows.

---

### 4. Production Database Monitoring with pg_stat_activity

Active connections and long-running queries were monitored using PostgreSQL's built-in process monitor:

```sql
SELECT pid, state, query, wait_event_type, now() - query_start AS duration
FROM pg_stat_activity
WHERE datname = 'weatheralerts'
AND state != 'idle';
```

This replicates how a DBA or SRE would monitor a production database for slow queries, blocked connections, or runaway processes — without needing an external tool.

---

## Infrastructure — Terraform

All three VMs, the VNet, subnet, NSGs, and public IP are provisioned with Terraform.

**Security group design:**
- Nginx VM — inbound 80, 443, 22 from anywhere
- App VMs — inbound 8000 only from the internal subnet (10.0.1.0/24), not from the internet

This means the FastAPI app servers are never directly reachable from the public internet — all traffic must pass through Nginx.

```bash
terraform init
terraform plan
terraform apply
```

---

## How to Run

### Prerequisites
- Azure CLI authenticated (`az login`)
- Terraform installed
- SSH key pair at `~/.ssh/id_rsa`

### 1. Provision infrastructure
```bash
cd terraform
terraform apply
```

### 2. Set up app VMs
SSH into each app VM via the Nginx VM as a jump host:
```bash
ssh -J azureuser@<nginx-public-ip> azureuser@10.0.1.5
```

Install and start the app:
```bash
mkdir ~/weatherapp && cd ~/weatherapp
python3 -m venv venv && source venv/bin/activate
pip install fastapi uvicorn
# copy main.py
sudo systemctl enable weatherapp && sudo systemctl start weatherapp
```

### 3. Configure Nginx
```bash
ssh azureuser@<nginx-public-ip>
sudo nginx -t && sudo systemctl restart nginx
```

### 4. Run zero-downtime deployment
```bash
sudo ~/deploy.sh
```

### 5. Deallocate VMs when not in use
```bash
az vm deallocate --resource-group nginx-project-rg --name nginx-vm
az vm deallocate --resource-group nginx-project-rg --name app-vm-1
az vm deallocate --resource-group nginx-project-rg --name app-vm-2
```

---

## Key Learnings

- `limit_req_zone` must be defined in the `http` block, not inside a `server` block
- PostgreSQL's query planner makes cost-based decisions — adding an index does not guarantee it will be used; selectivity determines whether the planner prefers an index scan or a sequential scan
- Zero-downtime deployments don't require Kubernetes — Nginx upstream `down` flags combined with health checks achieve the same result with far less infrastructure overhead
- Systemd service `status=203/EXEC` means the binary path in `ExecStart` is wrong — always verify the path with `which` before writing the service file

---

## Repository Structure

```
├── terraform/
│   ├── main.tf          # Provider, resource group, VNet, NSGs
│   ├── vms.tf           # VM definitions and NICs
│   ├── variables.tf     # Input variables
│   ├── outputs.tf       # IP address outputs
│   └── terraform.tfvars # Your values (gitignored)
├── app/
│   └── main.py          # FastAPI application
├── nginx/
│   └── weatherapp       # Nginx site config
├── scripts/
│   └── deploy.sh        # Zero-downtime deployment script
├── db/
│   ├── schema.sql       # Database schema
│   └── seed_data.py     # Data seeding script
└── README.md
```

---

*Infrastructure destroyed on Azure using terraform destroy. All VMs deallocated when not in use to minimise cost (~$0.06/hour when running).*
