import json
import logging
import os
import time
import uuid

import boto3
import psycopg2

from quizgen import generate_questions

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quiz-worker")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
QUIZZES_BUCKET = os.environ["QUIZZES_BUCKET"]
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["QUIZ_DB_NAME"]
DB_USER = os.environ["QUIZ_DB_USER"]
DB_PASSWORD = os.environ["QUIZ_DB_PASSWORD"]

s3 = boto3.client("s3", region_name=AWS_REGION)
sqs = boto3.client("sqs", region_name=AWS_REGION)
sns = boto3.client("sns", region_name=AWS_REGION)

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
    # This runs from both worker.py's process and app.py's gunicorn process
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


def process_message(document_id: str, text: str):
    questions = generate_questions(text, max_questions=5)

    quiz_id = str(uuid.uuid4())
    s3_key = f"quizzes/{document_id}/quiz.json"
    payload = {
        "document_id": document_id,
        "quiz_id": quiz_id,
        "questions": questions,
    }
    s3.put_object(
        Bucket=QUIZZES_BUCKET,
        Key=s3_key,
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )
    log.info("stored s3://%s/%s (%d questions)", QUIZZES_BUCKET, s3_key, len(questions))

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO quizzes (id, document_id, s3_key, question_count, status)
                VALUES (%s, %s, %s, %s, 'ready')
                ON CONFLICT (document_id) DO UPDATE
                    SET s3_key = EXCLUDED.s3_key,
                        question_count = EXCLUDED.question_count,
                        status = 'ready'
                """,
                (quiz_id, document_id, s3_key, len(questions)),
            )
    finally:
        conn.close()

    if SNS_TOPIC_ARN:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="Your quiz is ready",
            Message=json.dumps({
                "document_id": document_id,
                "quiz_id": quiz_id,
                "question_count": len(questions),
            }),
        )
        log.info("published SNS notification for document %s", document_id)


def main():
    init_db()
    log.info("quiz worker polling %s", SQS_QUEUE_URL)
    while True:
        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=20,
            VisibilityTimeout=60,
        )
        messages = response.get("Messages", [])
        if not messages:
            continue

        for message in messages:
            receipt_handle = message["ReceiptHandle"]
            try:
                body = json.loads(message["Body"])
                document_id = body["document_id"]
                text = body.get("text", "")
                log.info("processing document %s (%d chars)", document_id, len(text))
                process_message(document_id, text)
                sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
                log.info("done with document %s", document_id)
            except Exception:
                log.exception("failed to process message %s, leaving on queue for retry", message.get("MessageId"))
                time.sleep(2)


if __name__ == "__main__":
    main()
