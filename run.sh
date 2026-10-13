#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"

PORT="${PORT:-8010}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-$HOME/ollama-models}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

# 1. Locate the ollama binary (standard install or portable user-space tarball)
OLLAMA_BIN="$(command -v ollama 2>/dev/null || true)"
if [[ -z "${OLLAMA_BIN}" ]]; then
  for p in /usr/local/bin/ollama /usr/bin/ollama "$HOME/ollama-dist/bin/ollama"; do
    [[ -x "$p" ]] && OLLAMA_BIN="$p" && break
  done
fi
if [[ -z "${OLLAMA_BIN}" ]]; then
  echo "ERROR: ollama not found. Install via: curl -fsSL https://ollama.com/install.sh | sh"
  exit 1
fi
export LD_LIBRARY_PATH="$(dirname "$OLLAMA_BIN")/../lib/ollama:${LD_LIBRARY_PATH:-}"

# 2. Ensure the Ollama server is running
if ! curl -s -m 3 -o /dev/null "$OLLAMA_BASE_URL/api/tags"; then
  echo "[run] starting Ollama server…"
  mkdir -p "$OLLAMA_MODELS"
  setsid nohup "$OLLAMA_BIN" serve > "$OLLAMA_MODELS/serve.log" 2>&1 < /dev/null & disown
  sleep 4
  curl -s -m 3 -o /dev/null "$OLLAMA_BASE_URL/api/tags" || {
    echo "ERROR: Ollama server did not start. See $OLLAMA_MODELS/serve.log"; exit 1;
  }
fi

# 3. Ensure the LLM is available
if ! curl -s "$OLLAMA_BASE_URL/api/tags" | grep -q '"llama3.2:3b"'; then
  echo "[run] pulling llama3.2:3b (first run, may take a while)…"
  "$OLLAMA_BIN" pull llama3.2:3b
fi

# 4. Python environment
if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "[run] setting up Python environment…"
  command -v uv >/dev/null 2>&1 || { curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }
  uv venv --clear .venv
  uv pip install --python .venv/bin/python -r backend/requirements.txt
fi

# 5. Start the web app
echo "[run] Consultant Work-Log Bot → http://localhost:${PORT}"
exec .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT"
