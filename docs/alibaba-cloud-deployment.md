# Alibaba Cloud Deployment Proof

This file demonstrates that Qwen Council is deployed and running on Alibaba Cloud infrastructure.

## Live Deployment

- **Public URL**: http://47.84.227.185
- **Health Check**: http://47.84.227.185/health
- **API Base**: http://47.84.227.185/api

## Alibaba Cloud Services Used

### 1. Elastic Compute Service (ECS)

| Property | Value |
|----------|-------|
| **Service** | Alibaba Cloud ECS |
| **Instance Type** | ecs.t6-c1m2.large |
| **vCPU** | 2 |
| **Memory** | 4 GB |
| **OS** | Ubuntu 22.04 LTS |
| **Region** | ap-southeast-1 (Singapore) |
| **Public IP** | 47.84.227.185 |
| **Security Group** | Allow inbound TCP 80 (HTTP), 22 (SSH) |

The ECS instance hosts the entire application stack via Docker Compose:
- Nginx reverse proxy (port 80)
- FastAPI backend (port 8000, internal)
- PostgreSQL 15 with pgvector (port 5432, internal)

**Evidence**: The `docker-compose.yml` in this repository defines all three services and is deployed directly on this ECS instance.

### 2. Qwen Cloud API (DashScope)

| Property | Value |
|----------|-------|
| **Service** | Qwen Cloud (DashScope International) |
| **API Base** | https://dashscope-intl.aliyuncs.com/compatible-mode/v1 |
| **Models Used** | qwen3-coder-plus, qwen-vl-plus, text-embedding-v3 |
| **Authentication** | API key via `DASHSCOPE_API_KEY` environment variable |

The backend connects to Qwen Cloud API for all LLM operations:
- **qwen3-coder-plus**: Code analysis, agent responses, answer synthesis
- **qwen-vl-plus**: Visual inspection of screenshots and architecture diagrams
- **text-embedding-v3**: Semantic memory embeddings (1536-dimensional vectors)

**Evidence**: See `backend/config.py` (line 12) and `backend/agents/base_agent.py` (line 38-42) for API configuration.

### 3. Container Registry (ACR) — Optional

Docker images can be pushed to Alibaba Cloud Container Registry (ACR) for automated deployment. The current deployment uses direct `git pull` + `docker compose build` on the ECS instance.

## Deployment Script

The `deploy.sh` script in this repository automates the full deployment on Alibaba Cloud ECS:

```bash
#!/usr/bin/env bash
# deploy.sh — Deploy Qwen Council on Alibaba Cloud ECS
#
# Prerequisites:
#   - Alibaba Cloud ECS instance (Ubuntu 22.04+)
#   - SSH access as root
#   - .env file with qwen_api_key
#
# Steps:
#   1. Install Docker and Docker Compose if missing
#   2. Pull latest code from GitHub
#   3. Build all Docker images
#   4. Start PostgreSQL, Backend, and Frontend
#   5. Run health checks
#   6. Execute smoke test

set -euo pipefail

echo "=== Qwen Council — Alibaba Cloud ECS Deployment ==="

# Step 1: Install Docker if missing
if ! command -v docker &> /dev/null; then
    echo "[1/6] Installing Docker..."
    apt-get update
    apt-get install -y docker.io docker-compose-v2
    systemctl enable docker
    systemctl start docker
else
    echo "[1/6] Docker already installed: $(docker --version)"
fi

# Step 2: Pull latest code
echo "[2/6] Pulling latest code..."
git pull origin main

# Step 3: Build
echo "[3/6] Building Docker images..."
docker compose build

# Step 4: Start services
echo "[4/6] Starting services..."
docker compose down
docker compose up -d

# Step 5: Health check
echo "[5/6] Waiting for services to start..."
sleep 10
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80/health)
if [ "$HTTP_CODE" = "200" ]; then
    echo "[OK] Health check passed (HTTP $HTTP_CODE)"
else
    echo "[FAIL] Health check failed (HTTP $HTTP_CODE)"
    exit 1
fi

# Step 6: Smoke test
echo "[6/6] Running smoke test..."
RESPONSE=$(curl -s -X POST http://localhost:80/api/review \
  -H 'Content-Type: application/json' \
  -d '{"code": "def hello(): return 1"}')

if echo "$RESPONSE" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    echo "[OK] Smoke test passed"
else
    echo "[FAIL] Smoke test failed"
    exit 1
fi

echo ""
echo "=== Deployment Complete ==="
echo "Frontend: http://$(curl -s ifconfig.me)"
echo "API:      http://$(curl -s ifconfig.me)/api"
```

## Verification

To verify the deployment is running on Alibaba Cloud ECS:

1. **Check the public IP**: `curl http://47.84.227.185/health` → returns `{"status": "ok"}`
2. **Check the ECS instance**: The IP `47.84.227.185` belongs to Alibaba Cloud's Singapore region (ap-southeast-1)
3. **Check the Qwen Cloud API**: The backend connects to `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` — Alibaba's Qwen Cloud API endpoint

## Repository Files Demonstrating Alibaba Cloud Usage

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Defines 3-service stack deployed on ECS |
| `deploy.sh` | Automated deployment script for ECS |
| `backend/config.py` | Qwen Cloud API configuration (dashscope-intl.aliyuncs.com) |
| `backend/agents/base_agent.py` | LLM client connecting to Qwen Cloud API |
| `docs/architecture.md` | Full system architecture diagram |
| `docs/alibaba-cloud-deployment.md` | This file |
