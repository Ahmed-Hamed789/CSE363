import io
import json
import logging
import os
import uuid

import boto3
import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request
from pypdf import PdfReader

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("document-service")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
DOCUMENTS_BUCKET = os.environ["DOCUMENTS_BUCKET"]
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DOCS_DB_NAME"]
DB_USER = os.environ["DOCS_DB_USER"]
DB_PASSWORD = os.environ["DOCS_DB_PASSWORD"]

MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "20")) * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

s3 = boto3.client("s3", region_name=AWS_REGION)
sqs = boto3.client("sqs", region_name=AWS_REGION)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    filename TEXT NOT NULL,
    content_type TEXT,
    size_bytes BIGINT NOT NULL,
    s3_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    extracted_text TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, connect_timeout=5,
    )


def init_db():
    # gunicorn boots multiple worker processes, each importing this module
    # and calling init_db() at the same instant -- an advisory lock keeps
    # concurrent "CREATE TABLE IF NOT EXISTS" calls from racing each other
    # (which Postgres does not make safe on its own).
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(913001)")
            try:
                cur.execute(SCHEMA)
            finally:
                cur.execute("SELECT pg_advisory_unlock(913001)")
    finally:
        conn.close()


def extract_text(filename: str, content_type: str, raw: bytes) -> str:
    lower = (filename or "").lower()
    try:
        if lower.endswith(".pdf") or content_type == "application/pdf":
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        return raw.decode("utf-8", errors="ignore").strip()
    except Exception:
        log.exception("text extraction failed for %s", filename)
        return ""


@app.get("/health")
def health():
    return "OK\n", 200, {"Content-Type": "text/plain"}


@app.post("/api/documents/upload")
def upload_document():
    if "file" not in request.files:
        return jsonify(error="multipart field 'file' is required"), 400

    upload = request.files["file"]
    if not upload.filename:
        return jsonify(error="no file selected"), 400

    raw = upload.read()
    if not raw:
        return jsonify(error="uploaded file is empty"), 400

    document_id = str(uuid.uuid4())
    s3_key = f"documents/{document_id}/{upload.filename}"

    s3.put_object(
        Bucket=DOCUMENTS_BUCKET,
        Key=s3_key,
        Body=raw,
        ContentType=upload.content_type or "application/octet-stream",
    )
    log.info("stored s3://%s/%s (%d bytes)", DOCUMENTS_BUCKET, s3_key, len(raw))

    text = extract_text(upload.filename, upload.content_type, raw)
    status = "queued" if text else "queued_empty_text"

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents
                    (id, filename, content_type, size_bytes, s3_key, status, extracted_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (document_id, upload.filename, upload.content_type, len(raw), s3_key, status, text),
            )
    finally:
        conn.close()

    sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps({"document_id": document_id, "text": text}),
    )
    log.info("queued document %s (%d chars extracted)", document_id, len(text))

    return jsonify(document_id=document_id, status=status), 202


@app.get("/api/documents")
def list_documents():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, filename, content_type, size_bytes, status, created_at
                FROM documents ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify([dict(r, id=str(r["id"]), created_at=r["created_at"].isoformat()) for r in rows])


@app.get("/api/documents/<document_id>")
def get_document(document_id):
    try:
        uuid.UUID(document_id)
    except ValueError:
        return jsonify(error="invalid document id"), 400

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify(error="document not found"), 404

    row = dict(row)
    row["id"] = str(row["id"])
    row["created_at"] = row["created_at"].isoformat()
    row["updated_at"] = row["updated_at"].isoformat()
    return jsonify(row)


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
