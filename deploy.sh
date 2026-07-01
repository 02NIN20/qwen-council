#!/usr/bin/env bash
# =============================================================================
#  deploy.sh — Qwen Council Deployment Script for Alibaba Cloud ECS
# =============================================================================
#  Usage:
#    1. SSH into your Alibaba ECS instance
#    2. Clone the repo:  git clone https://github.com/02NIN20/qwen-council.git
#    3. cd qwen-council
#    4. Create .env with your Qwen API key (see .env.example)
#    5. Run:  sudo bash deploy.sh
#
#  This script will:
#    - Install Docker & Docker Compose if missing
#    - Build and start all services (PostgreSQL, Backend, Frontend)
#    - Run health checks to verify everything is working
# =============================================================================

set -euo pipefail

# ── Colors ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Pre-flight checks ─────────────────────────────────────────────────────

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
    log_error ".env file not found!"
    echo ""
    echo "  Create .env from the template:"
    echo "    cp .env.example .env"
    echo ""
    echo "  Then edit .env and set your Qwen API key:"
    echo "    qwen_api_key=sk-your-key-here"
    echo ""
    exit 1
fi

# Strip Windows CRLF from .env if present, then source
if grep -rl $'\r' .env &>/dev/null; then
    log_warn ".env contains Windows CRLF line endings — stripping carriage returns"
    sed -i 's/\r$//' .env
fi

# Source .env to verify required variables
set -a
source .env
set +a

if [[ -z "${qwen_api_key:-}" ]]; then
    log_error "qwen_api_key is not set in .env"
    exit 1
fi

# ── Ensure Docker & Docker Compose are installed ──────────────────────────

log_info "Checking Docker installation..."

if ! command -v docker &>/dev/null; then
    log_warn "Docker not found. Installing..."
    curl -fsSL https://get.docker.com | bash
    sudo usermod -aG docker "$USER"
    log_ok "Docker installed. You may need to log out and back in for group changes."
else
    log_ok "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"
fi

if ! docker compose version &>/dev/null; then
    log_warn "Docker Compose plugin not found. Installing..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi
log_ok "Docker Compose $(docker compose version --short)"

# ── Build & start services ────────────────────────────────────────────────

log_info "Building Docker images (this may take a few minutes)..."
docker compose build --pull 2>&1 | tail -5

log_info "Starting services..."
# Export environment variables explicitly so Docker containers receive them
# (belt-and-suspenders: both environment and env_file)
set -a
source .env
set +a
docker compose up -d --remove-orphans

# ── Wait for health checks ────────────────────────────────────────────────

log_info "Waiting for services to be healthy..."

MAX_RETRIES=30
RETRY=0

while [[ $RETRY -lt $MAX_RETRIES ]]; do
    HEALTH=$(curl -sf http://localhost:80/api/health 2>/dev/null || echo "")
    if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
        log_ok "Backend API is healthy"
        break
    fi
    RETRY=$((RETRY + 1))
    echo -n "."
    sleep 2
done

if [[ $RETRY -eq $MAX_RETRIES ]]; then
    log_error "Backend API failed to start after ${MAX_RETRIES} attempts"
    log_info "Check logs:  docker compose logs backend"
    docker compose logs --tail=20 backend
    exit 1
fi

# Verify frontend is serving
FRONTEND_CHECK=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:80/ 2>/dev/null || echo "000")
if [[ "$FRONTEND_CHECK" == "200" ]]; then
    log_ok "Frontend is serving on http://localhost:80"
else
    log_warn "Frontend returned HTTP $FRONTEND_CHECK (might still be starting)"
fi

# ── Summary ────────────────────────────────────────────────────────────────

echo ""
log_info "========================================"
log_info "  Qwen Council is now running!"
log_info "========================================"
echo ""
echo "  Frontend:  http://$(curl -sf ifconfig.me 2>/dev/null || echo 'localhost')"
echo "  Backend:   (internal, proxied through nginx)"
echo "  API Docs:  http://$(curl -sf ifconfig.me 2>/dev/null || echo 'localhost')/docs"
echo ""
echo "  To view logs:"
echo "    docker compose logs -f backend"
echo "    docker compose logs -f frontend"
echo ""
echo "  To stop:"
echo "    docker compose down"
echo ""
echo "  To update:"
echo "    git pull && sudo bash deploy.sh"
echo ""

# ── Optional: run a quick test review ─────────────────────────────────────

log_info "Running quick smoke test..."
TEST_RESULT=$(curl -sf -X POST http://localhost:80/api/review \
    -H "Content-Type: application/json" \
    -d '{"code": "def hello():\n    return 1 + 1"}' 2>/dev/null || echo "")

if echo "$TEST_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('session_id') else 1)" 2>/dev/null; then
    # Check if findings are non-empty (API key working correctly)
    FINDING_COUNT=$(echo "$TEST_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('report',{}).get('findings',[])))" 2>/dev/null)
    if [[ "$FINDING_COUNT" -gt 0 ]]; then
        log_ok "Smoke test passed — $FINDING_COUNT findings returned (API key working)"
    else
        log_warn "Smoke test passed (session_id returned) but 0 findings — API key may not be reaching the container"
        log_info "Check backend logs:  docker compose logs --tail=30 backend"
    fi
else
    log_warn "Smoke test failed (expected if PostgreSQL just started)"
    log_info "The DB container may still be initializing. Wait a moment and try again."
    log_info "Backend logs:"
    docker compose logs --tail=20 backend 2>/dev/null || true
fi

echo ""
log_info "Deployment complete!"
