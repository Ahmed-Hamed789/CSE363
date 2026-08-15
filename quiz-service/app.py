import json
import logging
import os
import uuid

import boto3
import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quiz-service")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
QUIZZES_BUCKET = os.environ["QUIZZES_BUCKET"]

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["QUIZ_DB_NAME"]
DB_USER = os.environ["QUIZ_DB_USER"]
DB_PASSWORD = os.environ["QUIZ_DB_PASSWORD"]

app = Flask(__name__)
s3 = boto3.client("s3", region_name=AWS_REGION)

SCHEMA = """
CREATE TABLE IF NOT EXISTS quizzes (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL UNIQUE,
    s3_key TEXT NOT NULL,
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
"""


def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, connect_timeout=5,
    )


def init_db():
    # This runs from both the gunicorn API process and worker.py's process
    # at container start, at the same instant -- an advisory lock keeps
    # their concurrent "CREATE TABLE IF NOT EXISTS" calls from racing each
    # other (which Postgres does not make safe on its own).
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


def load_quiz_row(document_id: str):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM quizzes WHERE document_id = %s", (document_id,))
            return cur.fetchone()
    finally:
        conn.close()


def load_quiz_payload(s3_key: str) -> dict:
    obj = s3.get_object(Bucket=QUIZZES_BUCKET, Key=s3_key)
    return json.loads(obj["Body"].read())


@app.get("/health")
def health():
    return "OK\n", 200, {"Content-Type": "text/plain"}


@app.get("/api/quiz/<document_id>")
def get_quiz(document_id):
    try:
        uuid.UUID(document_id)
    except ValueError:
        return jsonify(error="invalid document id"), 400

    row = load_quiz_row(document_id)
    if not row:
        return jsonify(document_id=document_id, status="pending",
                        message="quiz has not been generated yet"), 200

    payload = load_quiz_payload(row["s3_key"])
    questions = [{"question": q["question"], "options": q["options"]} for q in payload["questions"]]

    return jsonify(
        document_id=document_id,
        quiz_id=str(row["id"]),
        status="ready",
        question_count=row["question_count"],
        questions=questions,
    )


@app.post("/api/quiz/<document_id>/submit")
def submit_quiz(document_id):
    try:
        uuid.UUID(document_id)
    except ValueError:
        return jsonify(error="invalid document id"), 400

    body = request.get_json(silent=True) or {}
    answers = body.get("answers")
    if not isinstance(answers, list):
        return jsonify(error="request body must be {'answers': [option_index, ...]}"), 400

    row = load_quiz_row(document_id)
    if not row:
        return jsonify(error="quiz not found for this document"), 404

    payload = load_quiz_payload(row["s3_key"])
    questions = payload["questions"]

    correct_count = 0
    for i, question in enumerate(questions):
        if i < len(answers) and answers[i] == question["answer_index"]:
            correct_count += 1

    total_count = len(questions)
    score = round(correct_count / total_count, 4) if total_count else 0.0
    submission_id = str(uuid.uuid4())

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO submissions
                    (id, document_id, answers, score, correct_count, total_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (submission_id, document_id, psycopg2.extras.Json(answers),
                 score, correct_count, total_count),
            )
    finally:
        conn.close()

    return jsonify(
        submission_id=submission_id,
        document_id=document_id,
        score=score,
        correct_count=correct_count,
        total_count=total_count,
    )


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
