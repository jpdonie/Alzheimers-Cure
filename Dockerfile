# Engine image (FastAPI). The web app deploys separately (Vercel). Secrets come from the host's environment variables, not the image.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY engine/requirements.txt engine/requirements.txt
RUN pip install --no-cache-dir -r engine/requirements.txt
COPY engine engine
ENV PYTHONUNBUFFERED=1 APPRENTICE_COOLDOWN=20
# data/ (transcripts, learned map, reviews, source PDFs) is mounted as a persistent volume at /app/data
EXPOSE 8000
CMD ["sh", "-c", "uvicorn engine.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
