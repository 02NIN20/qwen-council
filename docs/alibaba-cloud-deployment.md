# Alibaba Cloud ECS Deployment

## Instance Details

| Property | Value |
|----------|-------|
| **Instance ID** | `i-t4ngvwxej9256iz88jsq` |
| **Region / Zone** | `ap-southeast-1b` (Singapore) |
| **Public IP** | `47.84.227.185` |
| **OS** | Ubuntu 22.04 LTS (kernel 5.15.0-181-generic) |
| **Docker** | 3 containers running (frontend, backend, PostgreSQL) |
| **Status** | ✅ Healthy — all containers up since deployment |

## Architecture on ECS

```
Internet ──► nginx:80 (frontend) ──► backend:8000 ──► db:5432
                    ▲                      ▲              ▲
               React SPA              Uvicorn/FastAPI   pgvector
               (served by nginx)      (6 core agents)   (memory)
```

## Containers Running

```bash
$ docker ps
CONTAINER ID   IMAGE                      STATUS
fc8a7513574d   qwen-council-frontend      Up (healthy)
465bd2867d37   qwen-council-backend       Up (healthy)
e88ac8989f3f   pgvector/pgvector:pg15     Up (healthy)
```

## Deployment Method

```bash
git clone https://github.com/02NIN20/qwen-council.git
cd qwen-council
cp .env.example .env
# Configure Qwen API key and model
docker compose up --build -d
```

## Verification

```bash
# Health check
curl http://47.84.227.185/api/health
# → {"status":"ok","version":"1.0.0","db_connected":true}

# Frontend
curl -o /dev/null -w '%{http_code}' http://47.84.227.185/
# → 200
```

## API Key & Model

| Setting | Value |
|---------|-------|
| **Model** | `qwen3-plus` |
| **Vision Model** | `qwen-vl-max` |
| **Embedding Model** | `text-embedding-v3` |
| **Base URL** | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| **Timeout** | 300s |

## Cost Estimate

Based on Alibaba Cloud ECS pricing for Singapore region:

| Resource | Spec | Est. Monthly Cost |
|----------|------|-------------------|
| ECS Instance | 2 vCPU, 4 GiB, Ubuntu 22.04 | ~$25-35 USD |
| Elastic IP | 1 public IP (included) | Included |
| Total | | **~$25-35 USD/month** |

*Qwen API costs are usage-based (pay-per-token) and depend on review volume.*
