#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# AI Waiter — All-on-Pod startup script
# Run this once after the pod starts:  bash start_pod.sh
# ─────────────────────────────────────────────────────────────────
set -e

REPO_DIR="/workspace/AI-Waiter"
MODEL="tiiuae/Falcon-H1-7B-Instruct"
SIMPLE_MODEL="${SIMPLE_MODEL:-}"

echo "================================================"
echo "  AI Waiter — Pod Startup"
echo "================================================"

# ── 1. Qdrant ────────────────────────────────────────────────────
echo ""
echo "[1/4] Starting Qdrant..."
if [ "$(docker ps -q -f name=ai-waiter-qdrant)" ]; then
    echo "  Qdrant already running — skipping"
else
    docker run -d \
        --name ai-waiter-qdrant \
        -p 6333:6333 \
        -v qdrant_storage:/qdrant/storage \
        --restart unless-stopped \
        qdrant/qdrant:latest
    echo "  Waiting for Qdrant to be healthy..."
    until curl -sf http://localhost:6333/healthz > /dev/null; do sleep 2; done
    echo "  ✓ Qdrant ready"
fi

# ── 2. Install Python dependencies ───────────────────────────────
echo ""
echo "[2/4] Installing Python dependencies..."
cd "$REPO_DIR"
pip install -q -e . -r apps/api/requirements.txt
echo "  ✓ Dependencies installed"

# ── 3. Ingest menu into Qdrant ───────────────────────────────────
echo ""
echo "[3/4] Ingesting menu into Qdrant..."
python -m apps.api.scripts.ingest_menu
echo "  ✓ Menu ingested"

# ── 4. Start vLLM in background (tmux session) ───────────────────
echo ""
echo "[4/4] Starting Falcon H1 7B via vLLM on port 8001..."
tmux new-session -d -s vllm \
    "python -m vllm.entrypoints.openai.api_server \
        --model $MODEL \
        --guided-decoding-backend outlines \
        --port 8001 \
        --host 0.0.0.0 \
        --max-model-len 4096 \
        --enable-prefix-caching \
        2>&1 | tee /workspace/vllm.log"

echo "  Waiting for vLLM to load (this takes 2-5 minutes)..."
until curl -sf http://localhost:8001/health > /dev/null 2>&1; do
    sleep 5
    echo "  Still loading..."
done
echo "  ✓ vLLM ready"

# ── 5. Start FastAPI ─────────────────────────────────────────────
echo ""
echo "[5/5] Starting FastAPI on port 8000..."
tmux new-session -d -s api \
    "cd $REPO_DIR && uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 2>&1 | tee /workspace/api.log"

sleep 3
echo "  ✓ FastAPI ready"

# ── Done ─────────────────────────────────────────────────────────
echo ""
echo "================================================"
echo "  All services running!"
echo ""
echo "  FastAPI  → http://localhost:8000"
echo "             (public) https://YOUR_POD_ID-8000.proxy.runpod.net"
echo ""
echo "  vLLM     → http://localhost:8001"
echo "  Qdrant   → http://localhost:6333"
echo ""
echo "  Logs:"
echo "    tmux a -t api    ← FastAPI logs"
echo "    tmux a -t vllm   ← vLLM logs"
echo "================================================"
