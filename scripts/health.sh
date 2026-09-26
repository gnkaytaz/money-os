#!/usr/bin/env bash
set -euo pipefail
printf "API       "; curl -fsS http://localhost:${API_PORT:-8000}/health; echo
printf "SearXNG   "; curl -fsS "http://localhost:${SEARXNG_PORT:-8080}/search?q=automation&format=json" >/dev/null && echo OK
printf "Crawl4AI  "; curl -fsS http://localhost:${CRAWL4AI_PORT:-11235}/health >/dev/null && echo OK || echo "check dashboard: http://localhost:${CRAWL4AI_PORT:-11235}/dashboard"
printf "LiteLLM   "; curl -fsS http://localhost:${LITELLM_PORT:-4000}/health/liveliness >/dev/null && echo OK || echo "starting/not configured"
printf "n8n       "; curl -fsS http://localhost:${N8N_PORT:-5678}/healthz >/dev/null && echo OK
