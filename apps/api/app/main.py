import json
import os
import re
from typing import Any, Literal

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field, HttpUrl

DATABASE_URL = os.environ["DATABASE_URL"]
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")
CRAWL4AI_URL = os.getenv("CRAWL4AI_URL", "http://crawl4ai:11235")
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000/v1")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "sk-local-moneyos")
LITELLM_MODEL = os.getenv("LITELLM_MODEL", "money-local")
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "8"))
CRAWL_LIMIT = int(os.getenv("CRAWL_LIMIT", "5"))
MAX_PAGE_CHARS = int(os.getenv("MAX_PAGE_CHARS", "24000"))

app = FastAPI(title="Money OS API", version="0.1.0")
llm = OpenAI(base_url=LITELLM_URL, api_key=LITELLM_API_KEY)


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    search_limit: int = Field(default=SEARCH_LIMIT, ge=1, le=20)
    crawl_limit: int = Field(default=CRAWL_LIMIT, ge=1, le=10)


class FeedbackRequest(BaseModel):
    decision: Literal["approve", "reject", "interesting", "test", "kill", "paid", "paid_again"]
    reason: str | None = None
    correction: dict[str, Any] = Field(default_factory=dict)


class CrawlRequest(BaseModel):
    url: HttpUrl


def db():
    return psycopg.connect(DATABASE_URL)


@app.get("/health")
def health():
    return {"ok": True, "service": "money-os-api"}


async def search_web(query: str, limit: int) -> list[dict[str, Any]]:
    params = {"q": query, "format": "json", "language": "ru-RU"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{SEARXNG_URL}/search", params=params)
        r.raise_for_status()
        data = r.json()
    rows = []
    for i, item in enumerate(data.get("results", [])[:limit], start=1):
        url = item.get("url")
        if not url:
            continue
        rows.append({
            "rank": i,
            "url": url,
            "title": item.get("title") or "",
            "content": item.get("content") or "",
            "engine": ",".join(item.get("engines", [])) if isinstance(item.get("engines"), list) else item.get("engine"),
        })
    return rows


async def crawl_url(url: str) -> dict[str, Any]:
    # Keep the request on Crawl4AI's stable documented surface for v0.1.
    # Add browser/crawler config after the base loop is proven on your machine.
    payload = {"urls": [url], "priority": 10}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{CRAWL4AI_URL}/crawl", json=payload)
        r.raise_for_status()
        data = r.json()
        if "results" not in data and data.get("task_id"):
            task_id = data["task_id"]
            for _ in range(60):
                await __import__("asyncio").sleep(1)
                tr = await client.get(f"{CRAWL4AI_URL}/task/{task_id}")
                tr.raise_for_status()
                data = tr.json()
                if data.get("status") in {"completed", "failed"} or "results" in data:
                    break
    results = data.get("results") or []
    if not results:
        return {"url": url, "markdown": "", "ok": False, "raw": data}
    item = results[0]
    markdown = item.get("markdown") or item.get("cleaned_html") or item.get("html") or ""
    if isinstance(markdown, dict):
        markdown = markdown.get("raw_markdown") or markdown.get("fit_markdown") or json.dumps(markdown, ensure_ascii=False)
    return {"url": url, "markdown": str(markdown)[:MAX_PAGE_CHARS], "ok": True}


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\\s*", "", text)
        text = re.sub(r"\\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\\{.*\\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def ask_llm(query: str, evidence_rows: list[dict[str, Any]], feedback_examples: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_text = "\n\n".join(
        f"SOURCE {i+1}\nURL: {e['url']}\nTITLE: {e['title']}\nTEXT:\n{e['text']}"
        for i, e in enumerate(evidence_rows)
    )
    feedback_text = json.dumps(feedback_examples, ensure_ascii=False, indent=2)
    schema = {
        "problem": "specific expensive recurring problem",
        "buyer": "who controls budget",
        "current_solution": "how it is solved now",
        "evidence_summary": "what the sources actually establish",
        "existing_spend": "only sourced or explicitly unknown",
        "frequency": "low/medium/high + explanation",
        "urgency": "low/medium/high + explanation",
        "automation_feasibility": "low/medium/high + explanation",
        "competition": "low/medium/high/unknown + explanation",
        "regulatory_risk": "low/medium/high + explanation",
        "proposed_wedge": "one narrow product",
        "next_test": "smallest falsifiable experiment",
        "score": 0,
        "confidence": 0,
        "evidence_source_numbers": [1]
    }
    prompt = f"""You are the analyst inside Money OS.
Research question: {query}

Your job is NOT to invent startup ideas. Infer one concrete, recurring, expensive problem only if the supplied evidence supports it.
Separate facts from inference. Never invent revenue, payroll, budgets, market size, losses or willingness to pay.
If money cannot be established, write 'unknown'. Prefer problems where spend already exists.
Score 0-100 for worth investigating, not for attractiveness. Confidence 0-1.
Use prior human feedback as calibration examples, but do not blindly copy them.

PRIOR FEEDBACK:
{feedback_text}

EVIDENCE:
{evidence_text}

Return ONLY valid JSON matching this shape:
{json.dumps(schema, ensure_ascii=False, indent=2)}
"""
    response = llm.chat.completions.create(
        model=LITELLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return extract_json(response.choices[0].message.content or "{}")


def recent_feedback(limit: int = 12) -> list[dict[str, Any]]:
    sql = """
    SELECT o.problem, o.buyer, o.score, f.decision, f.reason, f.correction
    FROM feedback f
    JOIN opportunities o ON o.id = f.opportunity_id
    ORDER BY f.created_at DESC
    LIMIT %s
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
    return [
        {"problem": r[0], "buyer": r[1], "score": float(r[2]) if r[2] is not None else None,
         "decision": r[3], "reason": r[4], "correction": r[5]}
        for r in rows
    ]


@app.get("/search")
async def search(q: str, limit: int = 8):
    return {"query": q, "results": await search_web(q, min(max(limit, 1), 20))}


@app.post("/crawl")
async def crawl(req: CrawlRequest):
    return await crawl_url(str(req.url))


@app.post("/research")
async def research(req: ResearchRequest):
    with db() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO research_runs(query, status) VALUES (%s, 'running') RETURNING id", (req.query,))
        run_id = cur.fetchone()[0]
        conn.commit()

    search_results = await search_web(req.query, req.search_limit)
    evidence_rows: list[dict[str, Any]] = []

    for item in search_results[:req.crawl_limit]:
        crawled = await crawl_url(item["url"])
        text = crawled.get("markdown") or item.get("content") or ""
        if not text.strip():
            continue
        evidence_rows.append({**item, "text": text})
        with db() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO evidence(run_id, source_url, source_title, source_engine, source_rank, excerpt, raw_markdown)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (run_id, source_url) DO NOTHING""",
                (run_id, item["url"], item["title"], item.get("engine"), item["rank"], item.get("content"), text),
            )
            conn.commit()

    if not evidence_rows:
        raise HTTPException(422, "No usable evidence could be crawled")

    try:
        payload = ask_llm(req.query, evidence_rows, recent_feedback())
    except Exception as e:
        raise HTTPException(502, f"LLM extraction failed: {e}") from e

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunities(
                run_id, problem, buyer, current_solution, evidence_summary, existing_spend,
                frequency, urgency, automation_feasibility, competition, regulatory_risk,
                proposed_wedge, next_test, score, confidence, model_payload)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",
            (
                run_id, payload.get("problem") or "Unknown", payload.get("buyer"), payload.get("current_solution"),
                payload.get("evidence_summary"), payload.get("existing_spend"), payload.get("frequency"),
                payload.get("urgency"), payload.get("automation_feasibility"), payload.get("competition"),
                payload.get("regulatory_risk"), payload.get("proposed_wedge"), payload.get("next_test"),
                payload.get("score"), payload.get("confidence"), json.dumps(payload, ensure_ascii=False),
            ),
        )
        opportunity_id = cur.fetchone()[0]

        for n in payload.get("evidence_source_numbers", []):
            try:
                src = evidence_rows[int(n) - 1]
            except (ValueError, TypeError, IndexError):
                continue
            cur.execute("SELECT id FROM evidence WHERE run_id=%s AND source_url=%s", (run_id, src["url"]))
            found = cur.fetchone()
            if found:
                cur.execute(
                    "INSERT INTO opportunity_evidence(opportunity_id, evidence_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                    (opportunity_id, found[0]),
                )

        cur.execute("UPDATE research_runs SET status='completed', completed_at=now() WHERE id=%s", (run_id,))
        conn.commit()

    return {"run_id": str(run_id), "opportunity_id": str(opportunity_id), "opportunity": payload}


@app.get("/opportunities")
def opportunities(limit: int = 50):
    sql = """
    SELECT id, problem, buyer, existing_spend, proposed_wedge, next_test, score, confidence, created_at
    FROM opportunities ORDER BY created_at DESC LIMIT %s
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (min(max(limit, 1), 200),))
        rows = cur.fetchall()
    return [
        {"id": str(r[0]), "problem": r[1], "buyer": r[2], "existing_spend": r[3],
         "proposed_wedge": r[4], "next_test": r[5], "score": float(r[6]) if r[6] is not None else None,
         "confidence": float(r[7]) if r[7] is not None else None, "created_at": r[8].isoformat()}
        for r in rows
    ]


@app.post("/opportunities/{opportunity_id}/feedback")
def add_feedback(opportunity_id: str, req: FeedbackRequest):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM opportunities WHERE id=%s", (opportunity_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Opportunity not found")
        cur.execute(
            "INSERT INTO feedback(opportunity_id, decision, reason, correction) VALUES (%s,%s,%s,%s) RETURNING id",
            (opportunity_id, req.decision, req.reason, json.dumps(req.correction, ensure_ascii=False)),
        )
        feedback_id = cur.fetchone()[0]
        conn.commit()
    return {"ok": True, "feedback_id": str(feedback_id)}


@app.get("/feedback")
def feedback(limit: int = 100):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT f.id, f.opportunity_id, o.problem, f.decision, f.reason, f.correction, f.created_at
               FROM feedback f JOIN opportunities o ON o.id=f.opportunity_id
               ORDER BY f.created_at DESC LIMIT %s""",
            (min(max(limit, 1), 500),),
        )
        rows = cur.fetchall()
    return [
        {"id": str(r[0]), "opportunity_id": str(r[1]), "problem": r[2], "decision": r[3],
         "reason": r[4], "correction": r[5], "created_at": r[6].isoformat()}
        for r in rows
    ]
