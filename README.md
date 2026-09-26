# MONEY OS v0.1

A local-first research loop for finding **expensive, recurring business problems** and learning from your own decisions.

The point of v0.1 is deliberately narrow:

`query -> web search -> crawl evidence -> structured opportunity -> human feedback -> future calibration`

It is **not** an autonomous money printer and it does not fine-tune a model yet. The first learning loop retrieves your recent corrections and injects them into subsequent analyses. This is faster, reversible, and auditable. Fine-tuning comes later, after useful labels exist.

## Stack

- PostgreSQL — source of truth for runs, evidence, opportunities, feedback
- SearXNG — metasearch API
- Crawl4AI — page extraction
- LiteLLM — one OpenAI-compatible model gateway
- Ollama on macOS — local model runtime
- FastAPI — Money OS API
- n8n — orchestration/UI experiments later
- VS Code tasks — start, stop, health, logs, seed

## 0. Prerequisites

On Apple Silicon Mac:

- Docker Desktop
- VS Code
- `make`, `curl`, `python3` (macOS already has most of this; Homebrew is fine)
- Ollama installed natively on macOS

Install/pull a local model:

```bash
ollama pull qwen3:8b
ollama serve
```

If `ollama serve` says the address is already in use, the Ollama app is already serving it — that is fine.

## 1. Open in VS Code

```bash
cd money-os
code .
```

Copy environment config:

```bash
cp .env.example .env
```

For a local-only experiment, defaults are enough. Before exposing anything to a network, change all secrets and harden the services.

## 2. Start

```bash
make up
```

Or VS Code: **Terminal -> Run Task -> Money OS: Start stack**.

Then inspect:

- API docs: http://localhost:8000/docs
- n8n: http://localhost:5678
- SearXNG: http://localhost:8080
- Crawl4AI dashboard: http://localhost:11235/dashboard
- LiteLLM: http://localhost:4000

Check health:

```bash
make health
```

First startup may take longer while Docker downloads browser/model-service images.

## 3. First useful test

Open `requests.http` in VS Code and run the `Research` request, or:

```bash
make seed
```

The API performs:

1. SearXNG search.
2. Crawl up to N sources through Crawl4AI.
3. Save raw evidence in PostgreSQL.
4. Ask the local model to formulate **one** supported opportunity.
5. Store the opportunity and source links.

Inspect results:

```bash
curl -s http://localhost:8000/opportunities | python3 -m json.tool
```

## 4. Feedback loop

Copy an opportunity UUID and send feedback:

```bash
curl -s -X POST \
  http://localhost:8000/opportunities/OPPORTUNITY_UUID/feedback \
  -H 'Content-Type: application/json' \
  -d '{
    "decision":"reject",
    "reason":"already_solved_cheaply",
    "correction":{"note":"Existing SaaS solves this cheaply. Penalize similar cases."}
  }' | python3 -m json.tool
```

Supported decisions:

- `approve`
- `reject`
- `interesting`
- `test`
- `kill`
- `paid`
- `paid_again`

Recent feedback is supplied to the analyst on future research runs. This is v0.1's learning mechanism.

## 5. Database

```bash
make db-shell
```

Useful queries:

```sql
SELECT problem, buyer, score, confidence, created_at
FROM opportunities
ORDER BY created_at DESC;

SELECT o.problem, f.decision, f.reason, f.correction
FROM feedback f
JOIN opportunities o ON o.id = f.opportunity_id
ORDER BY f.created_at DESC;
```

## 6. What to build next

Do **not** add agents first. Collect 100-200 judgments.

Then implement in this order:

1. Similar-feedback retrieval (embeddings / pgvector or Qdrant only when needed).
2. Evidence ledger: claim-level source support and contradiction detection.
3. Opportunity clusters across many research runs.
4. A tiny review UI (`reject / interesting / test / why`).
5. Evaluation set and regression tests.
6. DSPy prompt optimization.
7. Ranker trained on your decisions.
8. Fine-tuning only after enough high-quality labels exist.
9. MAX/Mojo benchmark on a stable inference component.

The strongest target label is not `approve`; it is eventually `paid_again`.

## Architecture

```text
Question / hypothesis
        |
        v
     SearXNG
        |
        v
     Crawl4AI
        |
        v
 Evidence in Postgres
        |
        v
 LiteLLM -> Ollama local model
        |
        v
 Opportunity card
        |
        v
 Human decision + reason
        |
        +------> stored feedback
                   |
                   +----> calibration of future analyses
```

## Notes

- Respect each source's terms, robots policy, rate limits, privacy rules, and database rights. Publicly visible does not automatically mean unrestricted bulk reuse.
- Never let the model invent money numbers. `unknown` is a valid result.
- Keep raw evidence and model conclusions separate.
- Do not expose SearXNG, n8n, Crawl4AI, LiteLLM or PostgreSQL directly to the internet in this local configuration.
