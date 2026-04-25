#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# AI Waiter — Mac setup (Intel i9 or Apple Silicon, CPU inference via Ollama)
#
#   bash mac_setup.sh
#
# What it does:
#   1. Install Homebrew (if missing) + git, tmux, python@3.11, ollama
#   2. Start Ollama server
#   3. Pull a CPU-friendly Arabic-capable model (qwen2.5:7b-instruct)
#   4. Create a Python venv + install deps
#   5. Write apps/api/.env for Ollama
#   6. Ingest menu into embedded Qdrant
#   7. Launch FastAPI on :8001 in a tmux session
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/Ai-Projects/AI-Waiter}"
MODEL="${MODEL:-qwen2.5:1.5b-instruct}"
SIMPLE_MODEL="${SIMPLE_MODEL:-qwen2.5:0.5b-instruct}"
API_PORT="${API_PORT:-8001}"
OLLAMA_PORT=11434

banner() { echo -e "\n\033[1;33m==> $*\033[0m"; }

cd "$REPO_DIR"

banner "[1/7] Homebrew + dependencies"
if ! command -v brew >/dev/null 2>&1; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
brew install git tmux python@3.11 ollama curl || true

banner "[2/7] Start Ollama server"
if ! pgrep -x ollama >/dev/null 2>&1; then
  # Ollama installed as brew service OR via app — either works
  brew services start ollama 2>/dev/null || (nohup ollama serve > /tmp/ollama.log 2>&1 &)
  sleep 3
fi
until curl -sf http://localhost:${OLLAMA_PORT}/api/tags >/dev/null; do
  echo "  waiting for ollama…" ; sleep 2
done
echo "  ✓ Ollama up"

banner "[3/7] Pull models: $MODEL + $SIMPLE_MODEL"
ollama pull "$MODEL"
ollama pull "$SIMPLE_MODEL"

banner "[4/7] Python venv + deps"
if [ ! -d .venv ]; then
  python3.11 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e . -r apps/api/requirements.txt

banner "[5/7] Write apps/api/.env for Ollama"
cat > apps/api/.env <<EOF
LLM_BACKEND=ollama
LLM_API_BASE=http://localhost:${OLLAMA_PORT}/v1
LLM_API_KEY=ollama
LLM_MODEL_NAME=${MODEL}
LLM_SIMPLE_MODEL_NAME=${SIMPLE_MODEL}
LLM_NUM_CTX=1536
LLM_MAX_TOKENS=80
LLM_NUM_THREAD=0
LLM_KEEP_ALIVE=24h
LLM_WARMUP_ENABLED=true
CHAT_HISTORY_CHAR_BUDGET=320
QDRANT_PATH=${REPO_DIR}/qdrant_storage
QDRANT_COLLECTION=menu_ar
EMBEDDING_MODEL=BAAI/bge-m3
MENU_JSON_PATH=data/menu.json
IMAGES_DIR=data/images
EOF
echo "  .env written"

banner "[6/7] Ingest menu into embedded Qdrant"
rm -rf "${REPO_DIR}/qdrant_storage"
python -m apps.api.scripts.ingest_menu

banner "[7/7] Launch FastAPI on :${API_PORT}"
tmux kill-session -t api 2>/dev/null || true
tmux new-session -d -s api "cd $REPO_DIR && source .venv/bin/activate && \
  uvicorn apps.api.main:app --host 0.0.0.0 --port ${API_PORT} 2>&1 | tee /tmp/ai-waiter-api.log"
sleep 4

cat <<DONE

═════════════════════════════════════════════════════════════════
  ✅ AI Waiter is up on Mac.

  Ollama   http://localhost:11434   (model: $MODEL)
  FastAPI  http://localhost:${API_PORT}
  Qdrant   embedded at ${REPO_DIR}/qdrant_storage

  Logs:
    tmux a -t api          # Ctrl-B then D to detach
    tail -f /tmp/ollama.log

  Quick test:
    curl -X POST http://localhost:${API_PORT}/session/start

  Web app:
    cd apps/web
    echo "VITE_API_BASE=http://localhost:${API_PORT}" > .env
    npm install && npm run dev
═════════════════════════════════════════════════════════════════
DONE
