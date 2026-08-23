#!/usr/bin/env bash
set -euo pipefail

echo "=== Deploying governance-api to Google Cloud Run ==="

gcloud run deploy governance-api \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=3 \
  --memory=1Gi \
  --timeout=120 \
  --set-env-vars LLM_PROVIDER=gemini,ALLOWED_ORIGINS="https://governance-api.vercel.app,http://localhost:3000" \
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest
