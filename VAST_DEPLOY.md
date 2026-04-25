# Deploying AI Waiter on Vast.ai

This project runs best on Vast when you treat the GPU box as the **backend host**:

- `vLLM` serves the model
- `FastAPI` serves the application API
- embedded `Qdrant` stores menu vectors locally
- the web app can either be:
  - built and preview-served on the same box, or
  - deployed separately as a static site and pointed at the Vast backend

## Best Vast template

If you are **already using a Vast vLLM template**, keep it.

That is completely fine for this project as long as you do **not** reinstall the
older local-dev ML stack from `apps/api/requirements.txt`.

This repo now includes `apps/api/requirements-vllm.txt` specifically for cloud
hosts running modern `vLLM`, so the backend dependencies stay compatible with
the preinstalled `vLLM` environment.

## Recommended ports

Expose:

- `8001` for the backend API
- optionally `4173` for the web preview if you serve the frontend on Vast too

Keep private if possible:

- `8000` for the internal vLLM server

## Recommended Vast instance setup

- Template: your current `vLLM` template is okay
- Launch mode: `SSH`
- GPU: choose based on your model size
  - `RTX 4090` is usually enough for `Falcon-H1-7B-Instruct`
  - `L40S` or `A100 80GB` if you move to larger models or larger context
- Disk: at least `40-60 GB`
- SSH: enabled
- Public ports: `8001`, and optionally `4173`

## 1. Clone the repo on the Vast instance

```bash
cd /workspace
git clone https://github.com/ahmedshaikhkalil/AI-Waiter.git
cd AI-Waiter
```

## 2. Run the Vast provisioning script

Backend only:

```bash
bash vast_provision.sh
```

Backend + web preview on the same machine:

```bash
SERVE_WEB=true \
PUBLIC_API_BASE=https://YOUR-VAST-HOST-8001.vast.ai \
bash vast_provision.sh
```

If your model needs a Hugging Face token:

```bash
HF_TOKEN=hf_xxx \
MODEL=tiiuae/Falcon-H1-7B-Instruct \
bash vast_provision.sh
```

The script installs:

```text
apps/api/requirements-vllm.txt
```

and intentionally avoids the older local-dev ML pins in:

```text
apps/api/requirements.txt
```

## 3. Verify services

Backend:

```bash
curl http://localhost:8001/health
```

vLLM:

```bash
curl -H "Authorization: Bearer sk-change-me" http://localhost:8000/v1/models
```

Start a session:

```bash
curl -X POST http://localhost:8001/session/start
```

## 4. Connect the frontend

If you deploy the web app elsewhere, set:

```env
VITE_API_BASE=https://YOUR-VAST-HOST-8001.vast.ai
```

Then build or redeploy the frontend.

If you serve the web app on Vast with `SERVE_WEB=true`, open:

```text
https://YOUR-VAST-HOST-4173.vast.ai
```

## Logs

Attach to sessions:

```bash
tmux a -t vllm
tmux a -t api
tmux a -t web
```

Detach from tmux with:

```bash
Ctrl-b then d
```

## Notes

- The backend is single-process by design because session state is in-memory.
- If you want true production durability later, move sessions/orders/history out of memory to Redis or a database.
- Serving the frontend from Vast is okay for testing and demos. For production UX, it is better to host `apps/web/dist` on a static host and keep Vast for the API + model only.
