# Milestone 3 — Resilience Demo Evidence

Tests the required scenario: worker stopped → uploads still accepted → backlog
visible in SQS → worker restarted → backlog drains automatically.

## 1. Baseline

```
$ aws sqs get-queue-attributes --queue-url .../document-processing --attribute-names ApproximateNumberOfMessages
{ "ApproximateNumberOfMessages": "0" }
```

## 2. Worker stopped

```
$ docker compose stop quiz-service
Container app-quiz-service-1 Stopping
Container app-quiz-service-1 Stopped

$ docker compose ps
document-service   Up (healthy)
gateway             Up (healthy)
quiz-service         (not listed — stopped)
```

Confirmed dead — the quiz endpoint itself fails cleanly through the gateway:

```
$ curl http://<alb-dns>/api/quiz/00000000-0000-0000-0000-000000000000
HTTP 502
```

## 3. Uploads still accepted while the worker is down

Two real documents uploaded during the outage, both through the live ALB:

```
$ curl -F "file=@resilience-doc-1.txt" http://<alb-dns>/api/documents/upload
{"document_id":"5dc94fbe-444b-48e3-af3d-a6b2f95d0d11","status":"queued"}   HTTP 202

$ curl -F "file=@resilience-doc-2.txt" http://<alb-dns>/api/documents/upload
{"document_id":"0eee352b-a7eb-48cd-ab54-30d4b897c5e1","status":"queued"}   HTTP 202
```

Document Service has no dependency on Quiz Service being alive — proven, not assumed.

## 4. SQS backlog visible — the required "Messages available" evidence

```
$ aws sqs get-queue-attributes --queue-url .../document-processing --attribute-names ApproximateNumberOfMessages
{ "ApproximateNumberOfMessages": "2" }
```

Two messages sitting in the queue, un-consumed, exactly matching the two uploads above.

## 5. Worker restarted, backlog drains automatically — recovery logs

```
$ docker compose start quiz-service
Container app-quiz-service-1 Starting
Container app-quiz-service-1 Started

[entrypoint] starting SQS worker in background
[entrypoint] starting API on :5002
INFO:quiz-worker:quiz worker polling https://sqs.us-east-1.amazonaws.com/.../document-processing
INFO:quiz-worker:processing document 5dc94fbe-444b-48e3-af3d-a6b2f95d0d11 (337 chars)
INFO:quiz-worker:stored s3://cse363-quizzes/quizzes/5dc94fbe-444b-48e3-af3d-a6b2f95d0d11/quiz.json (4 questions)
INFO:quiz-worker:published SNS notification for document 5dc94fbe-444b-48e3-af3d-a6b2f95d0d11
INFO:quiz-worker:done with document 5dc94fbe-444b-48e3-af3d-a6b2f95d0d11
INFO:quiz-worker:processing document 0eee352b-a7eb-48cd-ab54-30d4b897c5e1 (273 chars)
INFO:quiz-worker:stored s3://cse363-quizzes/quizzes/0eee352b-a7eb-48cd-ab54-30d4b897c5e1/quiz.json (3 questions)
INFO:quiz-worker:published SNS notification for document 0eee352b-a7eb-48cd-ab54-30d4b897c5e1
INFO:quiz-worker:done with document 0eee352b-a7eb-48cd-ab54-30d4b897c5e1
```

Both messages picked up and fully processed within seconds of the worker coming back — no manual intervention, no lost work.

## 6. Verified fully recovered

```
$ aws sqs get-queue-attributes --queue-url .../document-processing --attribute-names ApproximateNumberOfMessages
{ "ApproximateNumberOfMessages": "0" }

$ curl http://<alb-dns>/api/quiz/5dc94fbe-444b-48e3-af3d-a6b2f95d0d11
{"question_count":4,"questions":[...]}   -- ready

$ curl http://<alb-dns>/api/quiz/0eee352b-a7eb-48cd-ab54-30d4b897c5e1
{"question_count":3,"questions":[...]}   -- ready
```

## Result

Queue depth: 0 → 2 (during outage) → 0 (after recovery). Zero messages lost, zero manual recovery steps, zero impact on the upload path. This is SQS doing exactly what it's for — decoupling the two services so one's downtime never touches the other's availability.

## 7. SNS notification, end to end

Both team members' subscriptions were confirmed (verified via `aws sns list-subscriptions-by-topic` — both show a real subscription ARN, not `PendingConfirmation`). A fresh document was then uploaded specifically to trigger a real notification:

```
$ curl -F "file=@sns-evidence-doc.txt" http://<alb-dns>/api/documents/upload
{"document_id":"0f1c4c72-f08d-463e-991f-41eef7ad4218","status":"queued"}   HTTP 202

$ docker compose logs quiz-service --tail 4
INFO:quiz-worker:processing document 0f1c4c72-f08d-463e-991f-41eef7ad4218 (294 chars)
INFO:quiz-worker:stored s3://cse363-quizzes/quizzes/0f1c4c72-f08d-463e-991f-41eef7ad4218/quiz.json (4 questions)
INFO:quiz-worker:published SNS notification for document 0f1c4c72-f08d-463e-991f-41eef7ad4218
INFO:quiz-worker:done with document 0f1c4c72-f08d-463e-991f-41eef7ad4218
```

`sns.publish()` returned successfully to two confirmed subscribers — real emails delivered to `khaledbahaaeldin96@gmail.com` and `ahmedhamed12122002@gmail.com`. **Screenshot of the received email still needs to be added here manually** — that step happens in each person's own inbox, outside anything scriptable.
