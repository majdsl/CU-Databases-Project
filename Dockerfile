FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY scripts/check_environment.py scripts/check_environment.py
# Storage unit tests import the host orchestrator; they mock all Docker calls.
COPY scripts/run_storage.py scripts/run_storage.py
COPY scripts/run_recovery.py scripts/run_recovery.py
COPY scripts/fetch_openflights.py scripts/fetch_openflights.py
COPY data/openflights data/openflights
COPY sql sql
COPY benchmarks benchmarks
COPY tests tests
# Non-secret provenance inputs for the result manifest.
COPY Dockerfile compose.yaml compose.runner-2cpu.yaml ./
COPY docker/mariadb docker/mariadb
USER 10001:10001
CMD ["python", "scripts/check_environment.py"]
