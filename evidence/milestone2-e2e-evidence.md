# Milestone 2 — End-to-End Evidence

All tests below ran against the live deployment through the real ALB:
`http://cse363-alb-614549833.us-east-1.elb.amazonaws.com` — no shortcuts, no
localhost, no mocked AWS calls.

## Containers up and healthy

```
$ docker compose ps
NAME                     STATUS                   PORTS
app-document-service-1   Up 9 minutes (healthy)   5001/tcp
app-gateway-1             Up 5 minutes (healthy)   0.0.0.0:80->80/tcp
app-quiz-service-1        Up 9 minutes (healthy)   5002/tcp
```

## Gateway routing (Nginx → both services)

```
$ curl -i http://<alb-dns>/health
HTTP/1.1 200 OK
OK

$ curl http://<alb-dns>/api/documents
[]
```

## Full upload → extract → queue → generate → serve → score flow

**1. Upload** (`POST /api/documents/upload`, a 9-sentence sample document about AWS/Docker/Nginx history):

```json
{"document_id":"ac2da7ef-aa70-4260-a19f-cf429fcc49ca","status":"queued"}
```
`HTTP 202` — returned immediately, before any quiz work started.

**2. Object landed in S3** (verified from the instance role, not just assumed):
```
2026-08-08 20:47:08        660 sample-doc.txt   (s3://cse363-documents/documents/ac2da7ef.../)
```

**3. Row written to docs_db**, full extracted text intact and matching the source file:
```
[('ac2da7ef-aa70-4260-a19f-cf429fcc49ca', 'sample-doc.txt', 'queued')]
```

**4. SQS → worker → quiz generation** (from the quiz-service container's own logs):
```
INFO:quiz-worker:processing document ac2da7ef-aa70-4260-a19f-cf429fcc49ca (659 chars)
INFO:quiz-worker:stored s3://cse363-quizzes/quizzes/ac2da7ef-aa70-4260-a19f-cf429fcc49ca/quiz.json (5 questions)
INFO:quiz-worker:published SNS notification for document ac2da7ef-aa70-4260-a19f-cf429fcc49ca
INFO:quiz-worker:done with document ac2da7ef-aa70-4260-a19f-cf429fcc49ca
```

**5. Quiz JSON in S3** (`cse363-quizzes`, verified from the instance role):
```
2026-08-08 20:47:08        898 quiz.json
```

**6. Row written to quiz_db**:
```
quizzes: [('a4f3497e-...', 'ac2da7ef-...', 5, 'ready')]
```

**7. `GET /api/quiz/{id}` serves 5 rule-based questions, no answers leaked:**

```json
{
  "document_id": "ac2da7ef-...", "status": "ready", "question_count": 5,
  "questions": [
    { "question": "The Relational Database Service supports PostgreSQL, MySQL, and _____ other database engines.",
      "options": ["2006", "4", "Simple", "2013"] },
    { "question": "Nginx was first released in _____ by Igor Sysoev.",
      "options": ["4", "Simple", "2013", "2004"] }
  ]
}
```

**8. `POST /api/quiz/{id}/submit` scores correctly** — tested both a partial and a perfect score:

```json
{"correct_count":3,"score":0.6,"submission_id":"e8c87d16-...","total_count":5}
{"correct_count":5,"score":1.0,"submission_id":"2cc60dcc-...","total_count":5}
```

Both submissions persisted to `quiz_db.submissions`:
```
[('ac2da7ef-...', 0.6, 3, 5), ('ac2da7ef-...', 1.0, 5, 5)]
```

**9. Error handling** — submitting to a quiz that doesn't exist returns `404`, not a 500 or a silent wrong answer.

## The isolation rule holds

At no point does the Quiz Service touch `docs_db` or `cse363-documents`, and at no point does the Document Service touch `quiz_db` or `cse363-quizzes` — verified both by code inspection (each service's `.env` only contains its own bucket/database credentials; there is no way for it to reach the other's) and by the fact the entire flow above only ever crossed between the two services via the SQS message.

## A real bug this testing caught

First boot, `quiz-service` crashed with `psycopg2.errors.UniqueViolation` on
`pg_type_typname_nsp_index` — `app.py` and `worker.py` both run
`CREATE TABLE IF NOT EXISTS` at startup, and Postgres does not make that
race-safe under true concurrency. Docker's restart policy silently retried
it into a passing state, which would have looked fine in a single quick
check and then failed unpredictably later (e.g. on a fresh clean-checkout
boot during grading). Fixed with a `pg_advisory_lock` around the schema
creation in all three entry points (`document-service/app.py`,
`quiz-service/app.py`, `quiz-service/worker.py`) so only one process ever
runs the DDL. See the fix commits for detail; re-tested clean after the fix
with no crash-restart in the logs.

A second bug — Nginx caching the upstream container IPs at startup, so
rebuilding just one backend service without touching the gateway leaves
it 502ing against a dead IP — was fixed by adding Docker's embedded DNS
resolver (`127.0.0.11`) with a short TTL in `nginx.conf`, so it re-resolves
`document-service`/`quiz-service` instead of caching forever.
