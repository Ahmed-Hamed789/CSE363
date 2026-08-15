# CSE363 Cloud-Based Learning Platform

A small cloud-native learning platform on AWS: upload a study document, it's
stored and its text extracted, a quiz is generated for it in the
background, and you take the quiz once it's ready.

Full design rationale and the required architecture diagram are in
[`docs/architecture.md`](docs/architecture.md) and the project [`report.md`](report.md).

## Architecture, in one paragraph

Nginx is the only thing the ALB talks to, and it routes by path:
`/api/documents/*` to the Document Service, `/api/quiz/*` to the Quiz
Service, `/health` to a 200. The Document Service owns the `cse363-documents`
bucket and `docs_db`; the Quiz Service owns `cse363-quizzes` and `quiz_db`.
The two services never touch each other's storage — the only thing that
crosses between them is a message on the `document-processing` SQS queue,
consumed by a worker thread inside the Quiz Service container, which
publishes to the `quiz-ready` SNS topic once a quiz exists.

## Running it locally

You need an `.env` with real values (copy `.env.example` — see below for
where each value comes from) and network access to the RDS instance and to
AWS (S3/SQS/SNS), so this is really meant to run **on the EC2 instance**,
which already has both via its instance role and VPC placement. It will
also run from a developer machine with valid AWS credentials exported in
the shell, provided your IP is allowed to reach the RDS security group.

```bash
cp .env.example .env      # fill in the values below
docker compose up -d --build
docker compose ps         # all three containers should show healthy
curl http://localhost/health
```

### Where the `.env` values come from

| Key | Value |
|---|---|
| `AWS_REGION` | `us-east-1` |
| `DOCUMENTS_BUCKET` | `cse363-documents` |
| `QUIZZES_BUCKET` | `cse363-quizzes` |
| `SQS_QUEUE_URL` | Output of `aws sqs get-queue-url --queue-name document-processing` |
| `SNS_TOPIC_ARN` | Output of `aws sns list-topics` (topic `quiz-ready`) |
| `DB_HOST` / `DB_PORT` | The `cse363-postgres` RDS endpoint, port `5432` |
| `DOCS_DB_NAME` / `DOCS_DB_USER` / `DOCS_DB_PASSWORD` | `docs_db` / `docs_user` / (from `secrets/db-credentials.txt`, never committed) |
| `QUIZ_DB_NAME` / `QUIZ_DB_USER` / `QUIZ_DB_PASSWORD` | `quiz_db` / `quiz_user` / (from `secrets/db-credentials.txt`, never committed) |

No AWS access key or secret key ever appears here — both services get
temporary credentials from the `CSE363-EC2-Role` instance profile via
instance metadata (hop limit 2, so the containers can reach it through the
bridge network).

## Deployed instance

Running on `cse363-app-1` behind `cse363-alb`:

```
http://cse363-alb-614549833.us-east-1.elb.amazonaws.com   (plain HTTP — for curl/testing)
https://d3fbanu3k36721.cloudfront.net                      (HTTPS front door for the same API)
```

**Use the app here, in a real browser:**

```
https://dmy1etit3nbyw.cloudfront.net
```

The static frontend (`frontend/index.html`) is uploaded to the public
`cse363-frontend` S3 bucket and served through that CloudFront distribution.
It isn't part of the Compose stack — it's a static file the browser loads
directly, which then calls the API distribution above (not the raw ALB
URL — that's plain HTTP, and an HTTPS page can't fetch from it; browsers
block that as mixed content). See [`report.md`](report.md) §11 for why
both distributions exist.

## Testing the API directly

```bash
# upload
curl -F "file=@sample.txt" http://<alb-dns>/api/documents/upload

# list
curl http://<alb-dns>/api/documents

# once the worker has processed it (a few seconds later)
curl http://<alb-dns>/api/quiz/<document_id>

# submit answers
curl -X POST http://<alb-dns>/api/quiz/<document_id>/submit \
  -H "Content-Type: application/json" -d '{"answers": [0,1,2,0,3]}'
```

Full endpoint reference: [`docs/api.md`](docs/api.md).

## Repository layout

```
document-service/   Flask API — upload, extract, store, enqueue
quiz-service/        Flask API + SQS worker — generate, serve, score
gateway/              Nginx reverse proxy — the ALB's only target
frontend/             Static upload/quiz UI, served from S3
iam-policies/         Per-bucket inline policies + the CLI operator policy
sql/                  Documented schema and the M1 user-creation script
docs/                 API reference and architecture notes
evidence/             Milestone 1 CLI evidence pack
```

## Credential hygiene

`.env` is git-ignored; only `.env.example` (empty values) is committed.
Database passwords and the EC2 team key live in `secrets/`, also
git-ignored. If you ever suspect a secret was committed, rotate it —
removing it from the latest commit is not enough, since it stays in
history.
