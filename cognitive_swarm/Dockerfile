# ==========================================
# STAGE 1: The Builder (The Factory)
# ==========================================
FROM python:3.11-slim-bullseye AS builder

RUN apt-get update && apt-get install -y gcc build-essential

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY cognitive_swarm/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==========================================
# STAGE 2: The Runner (The Vault)
# ==========================================
FROM python:3.11-slim-bullseye

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY proto /app/proto
COPY cognitive_swarm /app/cognitive_swarm

WORKDIR /app/cognitive_swarm

EXPOSE 8002
CMD ["python", "main.py"]