CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS research_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'created',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID REFERENCES research_runs(id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  source_title TEXT,
  source_engine TEXT,
  source_rank INTEGER,
  claim TEXT,
  excerpt TEXT,
  raw_markdown TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(run_id, source_url)
);

CREATE TABLE IF NOT EXISTS opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID REFERENCES research_runs(id) ON DELETE SET NULL,
  problem TEXT NOT NULL,
  buyer TEXT,
  current_solution TEXT,
  evidence_summary TEXT,
  existing_spend TEXT,
  frequency TEXT,
  urgency TEXT,
  automation_feasibility TEXT,
  competition TEXT,
  regulatory_risk TEXT,
  proposed_wedge TEXT,
  next_test TEXT,
  score NUMERIC(5,2),
  confidence NUMERIC(5,2),
  model_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS opportunity_evidence (
  opportunity_id UUID REFERENCES opportunities(id) ON DELETE CASCADE,
  evidence_id UUID REFERENCES evidence(id) ON DELETE CASCADE,
  PRIMARY KEY (opportunity_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  decision TEXT NOT NULL CHECK (decision IN ('approve','reject','interesting','test','kill','paid','paid_again')),
  reason TEXT,
  correction JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence(run_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_score ON opportunities(score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_feedback_opportunity ON feedback(opportunity_id);
