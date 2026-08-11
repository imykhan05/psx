# PSX AI Scanner API — Hugging Face Spaces (Docker SDK).
#
# Serves the read-only FastAPI backend on port 7860 (the HF Spaces app port).
# Installs requirements-api.txt ONLY — lean: no PySide6, no torch/transformers.
# Data files are baked in from the repo checkout and refreshed via git push
# (git-commit-on-refresh); the Space rebuilds on each push.

FROM python:3.12-slim

WORKDIR /app

# 1) Dependencies first so this (slow) layer is cached across data-only pushes.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# 2) Application code.
COPY api/ ./api/
COPY app/ ./app/
COPY config.py ./config.py

# 3) The data the API serves (only the git-tracked output files land here).
COPY database/ai_learning/ ./database/ai_learning/
COPY reports/latest/ ./reports/latest/

# HF Spaces proxies external HTTPS to the container's app_port (7860).
EXPOSE 7860

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
