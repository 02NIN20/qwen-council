# Hardware Constraints

## Alibaba ECS Deployment
- Target: Alibaba Cloud ECS instance
- Docker Compose based deployment
- CI/CD: GitHub Actions (`.github/workflows/deploy.yml`)

## Resource Constraints (TBD - to be updated during deployment)
- CPU/Memory: TBD based on ECS instance type
- Storage: TBD
- Network: TBD

## Known Constraints
- OpenAI SDK v2.x requires valid API key format even for mock tests
- Qwen API endpoint configurable via `QWEN_BASE_URL` env var
