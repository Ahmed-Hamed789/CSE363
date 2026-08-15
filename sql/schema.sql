-- Documented schema for both databases. The services themselves run these
-- exact statements (CREATE TABLE IF NOT EXISTS) on startup, so a fresh
-- `docker compose up -d --build` is enough to provision them — this file
-- is the reference copy, not a manual prerequisite step.

-- ============================================================
-- docs_db (owned exclusively by docs_user / Document Service)
-- ============================================================
\connect docs_db

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    filename TEXT NOT NULL,
    content_type TEXT,
    size_bytes BIGINT NOT NULL,
    s3_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',   -- uploaded | queued | queued_empty_text
    extracted_text TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- quiz_db (owned exclusively by quiz_user / Quiz Service)
-- ============================================================
\connect quiz_db

CREATE TABLE IF NOT EXISTS quizzes (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL UNIQUE,          -- the Document Service's id — never a foreign key
    s3_key TEXT NOT NULL,                      -- quiz JSON in cse363-quizzes
    question_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS submissions (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL,
    answers JSONB NOT NULL,
    score REAL NOT NULL,
    correct_count INTEGER NOT NULL,
    total_count INTEGER NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
