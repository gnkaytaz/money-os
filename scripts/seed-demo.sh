#!/usr/bin/env bash
set -euo pipefail
API=${API:-http://localhost:8000}
curl -sS -X POST "$API/research" \
  -H 'Content-Type: application/json' \
  -d '{"query":"бизнес вручную сверяет платежи сотрудники автоматизация стоимость процесса", "search_limit":6, "crawl_limit":3}' \
  | python3 -m json.tool
