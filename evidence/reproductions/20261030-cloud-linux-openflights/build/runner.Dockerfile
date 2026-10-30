FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --chmod=0755 requirements.txt .
RUN --mount=type=secret,id=cloud_ca,required=true PIP_CERT=/run/secrets/cloud_ca pip install --no-cache-dir --require-hashes -r requirements.txt
COPY --chmod=0755 scripts/check_environment.py scripts/check_environment.py
# Storage unit tests import the host orchestrator; they mock all Docker calls.
COPY --chmod=0755 scripts/run_storage.py scripts/run_storage.py
COPY --chmod=0755 scripts/run_recovery.py scripts/run_recovery.py
COPY --chmod=0755 scripts/fetch_openflights.py scripts/fetch_openflights.py
COPY --chmod=0755 scripts/setup_project.py scripts/setup_project.py
COPY --chmod=0755 scripts/run_cache_pressure.py scripts/run_cache_pressure.py
COPY --chmod=0755 scripts/run_write_diagnostics.py scripts/run_write_diagnostics.py
COPY --chmod=0755 scripts/run_rocksdb_compression.py scripts/run_rocksdb_compression.py
COPY --chmod=0755 data/openflights data/openflights
COPY --chmod=0755 sql sql
COPY --chmod=0755 benchmarks benchmarks
COPY --chmod=0755 tests tests
# Non-secret provenance inputs for the result manifest.
COPY --chmod=0755 Dockerfile compose.yaml compose.runner-2cpu.yaml ./
COPY --chmod=0755 docker/mariadb docker/mariadb
USER 10001:10001
CMD ["python", "scripts/check_environment.py"]
