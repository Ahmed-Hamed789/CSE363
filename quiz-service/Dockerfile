FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY quizgen.py worker.py app.py entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 5002

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5002/health').status==200 else 1)"

CMD ["bash", "entrypoint.sh"]
