#!/bin/bash
set -e

echo "[entrypoint] starting SQS worker in background"
python worker.py &
WORKER_PID=$!

term_handler() {
    echo "[entrypoint] shutting down worker $WORKER_PID"
    kill -TERM "$WORKER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
    exit 0
}
trap term_handler TERM INT

echo "[entrypoint] starting API on :5002"
gunicorn -b 0.0.0.0:5002 -w 2 --timeout 60 app:app &
API_PID=$!

wait -n "$WORKER_PID" "$API_PID"
EXIT_CODE=$?
echo "[entrypoint] a process exited (code $EXIT_CODE), stopping container"
kill -TERM "$WORKER_PID" "$API_PID" 2>/dev/null || true
exit "$EXIT_CODE"
