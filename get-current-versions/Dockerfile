FROM python:3.13-slim

# tzdata lets the TZ env var control when "midnight" is (defaults to UTC otherwise)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY get_versions.py serve.py ./
COPY assets/ ./assets/

ENV DATA_DIR=/data \
    PORT=80 \
    PYTHONUNBUFFERED=1

# State files (current.json / last.json) and versions.html live here,
# entirely inside the container - nothing is mounted from the host.
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:80/').read()" || exit 1

CMD ["python", "/app/serve.py"]
