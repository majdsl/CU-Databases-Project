FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY scripts/check_environment.py scripts/check_environment.py
COPY sql sql
USER 10001:10001
CMD ["python", "scripts/check_environment.py"]
