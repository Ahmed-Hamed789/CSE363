# API Reference

All routes are reached through the Nginx gateway, which is the only thing
the ALB talks to. Base URL in this deployment:

```
http://cse363-alb-614549833.us-east-1.elb.amazonaws.com
```

## Document Service

### `POST /api/documents/upload`

Multipart upload. Stores the file in `cse363-documents`, extracts its text,
writes a row to `docs_db`, and queues it for quiz generation. Returns
immediately — nothing waits on the quiz.

**Request**

```
curl -F "file=@notes.pdf" http://<alb-dns>/api/documents/upload
```

**Response** — `202 Accepted`

```json
{ "document_id": "b2e1...", "status": "queued" }
```

`status` is `queued_empty_text` if no extractable text was found (e.g. a
scanned image PDF) — the upload still succeeds.

---

### `GET /api/documents`

Lists uploaded documents, newest first.

**Response** — `200 OK`

```json
[
  {
    "id": "b2e1...",
    "filename": "notes.pdf",
    "content_type": "application/pdf",
    "size_bytes": 48213,
    "status": "queued",
    "created_at": "2026-08-08T21:14:03.221+00:00"
  }
]
```

---

### `GET /api/documents/{id}`

Full metadata for one document, including the extracted text.

**Response** — `200 OK` or `404` if the id doesn't exist.

---

### `GET /health`

Liveness check. `200 OK`, body `OK`.

## Quiz Service

### `GET /api/quiz/{id}`

`{id}` is the **document id** returned by the upload call — there is no
separate quiz id to track. Correct answers are never included in the
response.

**Before the worker has processed the document** — `200 OK`

```json
{ "document_id": "b2e1...", "status": "pending", "message": "quiz has not been generated yet" }
```

**Once ready** — `200 OK`

```json
{
  "document_id": "b2e1...",
  "quiz_id": "9f3a...",
  "status": "ready",
  "question_count": 5,
  "questions": [
    { "question": "AWS launched in _____.", "options": ["2006", "1998", "2011", "2015"] }
  ]
}
```

---

### `POST /api/quiz/{id}/submit`

`{id}` is the document id. Body is the selected option index per question,
in question order.

**Request**

```
curl -X POST http://<alb-dns>/api/quiz/b2e1.../submit \
  -H "Content-Type: application/json" \
  -d '{"answers": [0, 2, 1, 3, 0]}'
```

**Response** — `200 OK`

```json
{
  "submission_id": "1c7d...",
  "document_id": "b2e1...",
  "score": 0.8,
  "correct_count": 4,
  "total_count": 5
}
```

`404` if no quiz exists yet for that document id.

---

### `GET /health`

Liveness check. `200 OK`, body `OK`.

## Error shape

Every error response is `{ "error": "human-readable reason" }` with an
appropriate 4xx/5xx status.
