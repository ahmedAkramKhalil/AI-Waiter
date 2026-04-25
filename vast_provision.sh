#!/usr/bin/env bash
set -euo pipefail

# AI Waiter bootstrap for Vast.ai instances.
# Intended for recommended Vast templates, especially vastai/pytorch.
#
# Usage:
#   bash vast_provision.sh
#
# Optional environment variables:
#   MODEL=tiiuae/Falcon-H1-7B-Instruct
#   SIMPLE_MODEL=
#   VLLM_API_KEY=sk-change-me
#   VLLM_PORT=8000
#   API_PORT=8001
#   WEB_PORT=4173
#   MAX_MODEL_LEN=4096
#   GPU_MEMORY_UTILIZATION=0.85
#   SERVE_WEB=false
#   PUBLIC_API_BASE=https://YOUR-HOST-8001.vast.ai
#   HF_TOKEN=hf_xxx

banner() {
  echo ""
  echo "================================================"
  echo "  $*"
  echo "================================================"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${WORKSPACE:-/workspace}"
REPO_DIR="${REPO_DIR:-$SCRIPT_DIR}"
if [ ! -f "$REPO_DIR/pyproject.toml" ]; then
  REPO_DIR="${WORKSPACE}/AI-Waiter"
fi

MODEL="${MODEL:-tiiuae/Falcon-H1-7B-Instruct}"
SIMPLE_MODEL="${SIMPLE_MODEL:-}"
VLLM_PORT="${VLLM_PORT:-8000}"
API_PORT="${API_PORT:-8001}"
WEB_PORT="${WEB_PORT:-4173}"
VLLM_API_KEY="${VLLM_API_KEY:-sk-change-me}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.85}"
SERVE_WEB="${SERVE_WEB:-false}"
PUBLIC_API_BASE="${PUBLIC_API_BASE:-http://localhost:${API_PORT}}"
QDRANT_DIR="${QDRANT_DIR:-${WORKSPACE}/qdrant_storage}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_BIN="${PIP_BIN:-pip}"
TMUX_BIN="${TMUX_BIN:-tmux}"

if [ -n "${HF_TOKEN:-}" ]; then
  export HF_TOKEN
  export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
  export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
fi

banner "AI Waiter on Vast.ai"
echo "Repo dir: $REPO_DIR"
echo "Model:    $MODEL"
echo "API port: $API_PORT"
echo "vLLM:     $VLLM_PORT"
echo "Web:      $WEB_PORT (serve_web=$SERVE_WEB)"

if [ ! -f "$REPO_DIR/pyproject.toml" ]; then
  echo "Project not found at $REPO_DIR"
  echo "Clone the repo first or set REPO_DIR=/path/to/AI-Waiter"
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  banner "Installing system packages"
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    git tmux curl ca-certificates
fi

banner "Writing apps/api/.env"
cat > "$REPO_DIR/apps/api/.env" <<EOF
LLM_BACKEND=vllm
LLM_API_BASE=http://localhost:${VLLM_PORT}/v1
LLM_API_KEY=${VLLM_API_KEY}
LLM_MODEL_NAME=${MODEL}
LLM_SIMPLE_MODEL_NAME=${SIMPLE_MODEL}
LLM_NUM_CTX=1536
LLM_MAX_TOKENS=80
LLM_WARMUP_ENABLED=true
LLM_TEMPERATURE=0.15
LLM_TOP_P=0.85
LLM_CONNECT_TIMEOUT_S=10.0
LLM_REQUEST_RETRIES=1
LLM_RETRY_BACKOFF_MS=250
CHAT_HISTORY_CHAR_BUDGET=320
QDRANT_PATH=${QDRANT_DIR}
QDRANT_COLLECTION=menu_ar
EMBEDDING_MODEL=BAAI/bge-m3
RAG_RERANK_ENABLED=true
MENU_JSON_PATH=data/menu.json
IMAGES_DIR=data/images
EOF

banner "Installing Python dependencies"
cd "$REPO_DIR"
"$PIP_BIN" install -q --upgrade pip
"$PIP_BIN" install -q -e . -r apps/api/requirements.txt

banner "Ingesting menu into embedded Qdrant"
"$PYTHON_BIN" -m apps.api.scripts.ingest_menu

banner "Stopping previous sessions"
"$TMUX_BIN" kill-session -t vllm 2>/dev/null || true
"$TMUX_BIN" kill-session -t api 2>/dev/null || true
"$TMUX_BIN" kill-session -t web 2>/dev/null || true
pkill -9 -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
pkill -9 -f "uvicorn apps.api.main:app" 2>/dev/null || true
pkill -9 -f "vite preview --host 0.0.0.0 --port ${WEB_PORT}" 2>/dev/null || true
pkill -9 -f "ray" 2>/dev/null || true
sleep 2

banner "Starting vLLM"
VLLM_CMD="cd $REPO_DIR && \
  $PYTHON_BIN -m vllm.entrypoints.openai.api_server \
    --host 0.0.0.0 \
    --port $VLLM_PORT \
    --model $MODEL \
    --dtype auto \
    --api-key $VLLM_API_KEY \
    --max-model-len $MAX_MODEL_LEN \
    --gpu-memory-utilization $GPU_MEMORY_UTILIZATION \
    --enable-prefix-caching \
    2>&1 | tee $WORKSPACE/vllm.log"
"$TMUX_BIN" new-session -d -s vllm "$VLLM_CMD"

echo "Waiting for vLLM to load..."
until curl -sf -H "Authorization: Bearer $VLLM_API_KEY" \
  "http://localhost:${VLLM_PORT}/v1/models" > /dev/null 2>&1; do
  sleep 5
  echo "  still loading..."
done
echo "vLLM ready"

banner "Starting FastAPI"
API_CMD="cd $REPO_DIR && \
  uvicorn apps.api.main:app --host 0.0.0.0 --port $API_PORT \
  2>&1 | tee $WORKSPACE/api.log"
"$TMUX_BIN" new-session -d -s api "$API_CMD"
sleep 3
echo "FastAPI ready"

if [ "$SERVE_WEB" = "true" ]; then
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    banner "Building and serving web app"
    cd "$REPO_DIR/apps/web"
    export VITE_API_BASE="$PUBLIC_API_BASE"
    npm install
    npm run build
    WEB_CMD="cd $REPO_DIR/apps/web && \
      VITE_API_BASE=$PUBLIC_API_BASE npm run preview -- --host 0.0.0.0 --port $WEB_PORT \
      2>&1 | tee $WORKSPACE/web.log"
    "$TMUX_BIN" new-session -d -s web "$WEB_CMD"
    sleep 3
    echo "Web app ready"
  else
    echo "SERVE_WEB=true but node/npm are not installed. Skipping web startup."
    echo "Install Node 18+ and rerun, or deploy apps/web/dist on a static host."
  fi
fi

banner "Deployment complete"
echo "FastAPI health:  http://localhost:${API_PORT}/health"
echo "vLLM models:     http://localhost:${VLLM_PORT}/v1/models"
if [ "$SERVE_WEB" = "true" ]; then
  echo "Web preview:     http://localhost:${WEB_PORT}"
fi
echo ""
echo "tmux sessions:"
echo "  tmux a -t vllm"
echo "  tmux a -t api"
if [ "$SERVE_WEB" = "true" ]; then
  echo "  tmux a -t web"
fi
echo ""
echo "Publicly expose at least:"
echo "  - port ${API_PORT} for the backend"
if [ "$SERVE_WEB" = "true" ]; then
  echo "  - port ${WEB_PORT} for the frontend"
fi
