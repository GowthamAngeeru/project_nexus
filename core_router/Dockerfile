# ==========================================
# STAGE 1: The Builder (The Factory)
# ==========================================
FROM python:3.11-slim-bullseye AS builder

RUN apt-get update && apt-get install -y gcc build-essential

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy ONLY the requirements first to cache the pip install step
WORKDIR /app
COPY core_router/requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# ==========================================
# STAGE 2: The Runner (The Vault)
# ==========================================
FROM python:3.11-slim-bullseye

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy the Proto definitions AND the Router code
COPY proto /app/proto
COPY core_router /app/core_router

# Move into the router directory to run it
WORKDIR /app/core_router

EXPOSE 8001
CMD ["python", "main.py"]