#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# AI Waiter — full bootstrap for a fresh RunPod pod.
# One command from a clean shell:
#
#   REPO=https://github.com/YOU/AI-Waiter.git \
#   VLLM_API_KEY=sk-xxxx \
#   bash <(curl -sSL https://raw.githubusercontent.com/YOU/AI-Waiter/main/bootstrap.sh)
#
# Or, if the repo is already cloned:
#
#   bash bootstrap.sh
#
# What it does:
#   1. apt update + install git/tmux/curl
#   2. clone the repo into /workspace/AI-Waiter (if not present)
#   3. write apps/api/.env (vLLM @ :8000, embedded Qdrant)
#   4. pip install -e .  +  apps/api/requirements.txt
#   5. ingest data/menu.json into embedded Qdrant
#   6. launch vLLM (Falcon-H1-7B-Instruct)  in tmux session "vllm"  on :8000
#   7. wait for vLLM, then launch FastAPI    in tmux session "api"   on :8001
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO="${REPO:-https://github.com/ahmedshaikhkalil/AI-Waiter.git}"
# Default workspace root — overridden on vLLM base images that use /vllm-workspace
WORKSPACE="${WORKSPACE:-/workspace}"
[ -d /vllm-workspace ] && [ ! -d /workspace ] && WORKSPACE=/vllm-workspace
REPO_DIR="${REPO_DIR:-$WORKSPACE/AI-Waiter}"
QDRANT_DIR="${QDRANT_DIR:-$WORKSPACE/qdrant_storage}"
MODEL="${MODEL:-tiiuae/Falcon-H1-7B-Instruct}"
SIMPLE_MODEL="${SIMPLE_MODEL:-}"
VLLM_PORT="${VLLM_PORT:-8000}"
API_PORT="${API_PORT:-8001}"
VLLM_API_KEY="${VLLM_API_KEY:-sk-change-me}"

banner() { echo -e "\n\033[1;33m==> $*\033[0m"; }

banner "[1/6] apt update + install git/tmux/curl"
apt-get update -y
apt-get install -y --no-install-recommends git tmux curl ca-certificates

banner "[2/6] Cloning repo → $REPO_DIR"
mkdir -p "$(dirname "$REPO_DIR")"
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone "$REPO" "$REPO_DIR"
else
  echo "  already cloned — pulling latest"
  git -C "$REPO_DIR" pull --ff-only
fi
cd "$REPO_DIR"

banner "[3/6] Writing apps/api/.env"
cat > apps/api/.env <<EOF
LLM_BACKEND=vllm
LLM_API_BASE=http://localhost:${VLLM_PORT}/v1
LLM_API_KEY=${VLLM_API_KEY}
LLM_MODEL_NAME=${MODEL}
LLM_SIMPLE_MODEL_NAME=${SIMPLE_MODEL}
LLM_NUM_CTX=1536
LLM_MAX_TOKENS=80
LLM_WARMUP_ENABLED=true
CHAT_HISTORY_CHAR_BUDGET=320
QDRANT_PATH=${QDRANT_DIR}
QDRANT_COLLECTION=menu_ar
EMBEDDING_MODEL=BAAI/bge-m3
MENU_JSON_PATH=data/menu.json
IMAGES_DIR=data/images
EOF
echo "  .env written"

banner "[4/6] Installing Python deps"
pip install -q --upgrade pip
pip install -q -e . -r apps/api/requirements.txt

banner "[5/6] Ingesting menu into embedded Qdrant"
python -m apps.api.scripts.ingest_menu

banner "[6/6] Launching vLLM + FastAPI in tmux"

# Kill any previous sessions with the same names
tmux kill-session -t vllm 2>/dev/null || true
tmux kill-session -t api  2>/dev/null || true

# Nuke any orphan vLLM / uvicorn processes still holding VRAM.
# vLLM renames its worker to "VLLM::EngineCore" so we also kill every
# PID reported by nvidia-smi as holding compute memory.
pkill -9 -f "vllm"           2>/dev/null || true
pkill -9 -f "VLLM"           2>/dev/null || true
pkill -9 -f "uvicorn apps.api" 2>/dev/null || true
pkill -9 -f "ray"            2>/dev/null || true
if command -v nvidia-smi >/dev/null 2>&1; then
  for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
    echo "  killing GPU-holding PID $pid"
    kill -9 "$pid" 2>/dev/null || true
  done
fi
sleep 5
echo "  GPU memory after cleanup:"
nvidia-smi --query-gpu=memory.used,memory.free --format=csv 2>/dev/null || true

# vLLM
tmux new-session -d -s vllm "cd $REPO_DIR && \
  python -m vllm.entrypoints.openai.api_server \
    --host 0.0.0.0 \
    --port $VLLM_PORT \
    --model $MODEL \
    --dtype bfloat16 \
    --api-key $VLLM_API_KEY \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.75 \
    --enable-prefix-caching \
    2>&1 | tee /workspace/vllm.log"

echo "  waiting for vLLM to be ready on :$VLLM_PORT (may take 2–5 min)…"
until curl -sf -H "Authorization: Bearer $VLLM_API_KEY" \
        http://localhost:${VLLM_PORT}/v1/models > /dev/null 2>&1; do
  sleep 5
  echo "    still loading…"
done
echo "  ✓ vLLM ready"

# FastAPI
tmux new-session -d -s api "cd $REPO_DIR && \
  uvicorn apps.api.main:app --host 0.0.0.0 --port $API_PORT \
    2>&1 | tee /workspace/api.log"
sleep 3

cat <<DONE

═════════════════════════════════════════════════════════════════
  ✅ AI Waiter is up.

  FastAPI   http://0.0.0.0:${API_PORT}       (expose this one publicly)
  vLLM      http://0.0.0.0:${VLLM_PORT}
  Qdrant    embedded at /workspace/qdrant_storage

  Logs:
    tmux a -t api     # Ctrl-B then D to detach
    tmux a -t vllm

  Quick test:
    curl -X POST http://localhost:${API_PORT}/session/start
═════════════════════════════════════════════════════════════════
DONE
