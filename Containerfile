FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 FLUXTUNER_DATA_DIR=/data

WORKDIR /app

COPY pyproject.toml README.md ./
COPY fluxtuner ./fluxtuner

RUN python -m pip install --upgrade pip \
  && python -m pip install ".[web]" \
  && adduser --disabled-password --gecos "" --home /home/fluxtuner fluxtuner \
  && mkdir -p /data \
  && chown -R fluxtuner:fluxtuner /data /home/fluxtuner

USER fluxtuner

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
CMD python -c "import json, urllib.request; json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3))"

CMD ["fluxtuner-web", "--host", "0.0.0.0", "--port", "8080"]
