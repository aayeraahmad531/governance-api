# Deployment & Configuration Guide

This document contains the step-by-step pre-deployment checklist for deploying the **Governance API** backend to Google Cloud Run (`asia-south1`) and the **web frontend** to Vercel.

---

## 1. Secret Manager Setup (One-Time Prerequisites)

Before deploying to Cloud Run, create the `GEMINI_API_KEY` secret in Google Secret Manager and grant the default compute service account read access to it:

```bash
# 1. Create the secret from your API key string
echo -n "<YOUR_GEMINI_API_KEY>" | gcloud secrets create GEMINI_API_KEY --data-file=-

# 2. Grant the default compute service account permission to access the secret
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 2. Deploy the Backend to Google Cloud Run

Run the following command from the root of the repository to build and deploy the service:

```bash
gcloud run deploy governance-api \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --port 8080 \
  --min-instances=0 \
  --max-instances=3 \
  --memory=1Gi \
  --timeout=120 \
  --set-env-vars LLM_PROVIDER=gemini,DEBUG=false,ALLOWED_ORIGINS="<YOUR_VERCEL_URL>" \
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest
```

### Why Each Flag Matters
- `--max-instances=3`: Acts as a **hard cost ceiling** preventing runaway billing spikes on a public endpoint.
- `--set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest`: Keeps secret keys out of shell history and plain-text env vars in the Cloud Run console.
- `--region asia-south1`: Deploys to **Mumbai**, minimizing latency for clients in India (compared to `us-central1` which adds hundreds of ms round-trip).
- `--timeout=120`: Accommodates worst-case multi-turn retrieval/LLM latency on the `/api/hallucination` endpoint without 504 gateway timeouts.
- `--set-env-vars ALLOWED_ORIGINS="<YOUR_VERCEL_URL>"`: Configures CORS to whitelist only your frontend Vercel URL.

> [!CAUTION]
> **REVERSAL CALLOUT**: `ALLOWED_ORIGINS` in Cloud Run takes your **Vercel frontend URL** (e.g., `https://your-app.vercel.app`), NOT the Cloud Run URL! Setting this to the Cloud Run URL will cause browser CORS blocks.

---

## 3. Retrieve Your Deployed Cloud Run URL

Once deployment completes, retrieve your Cloud Run URL:

```bash
gcloud run services describe governance-api --region asia-south1 --format 'value(status.url)'
```

*Example Output*: `https://governance-api-abc123xyz-el.a.run.app`

---

## 4. Update the THREE Required URL Locations

You must paste your deployed URLs into **exactly THREE places**:

| Location | File / Config | Target Value | Purpose |
| :--- | :--- | :--- | :--- |
| **1. Frontend JS** | `web/assets/site.js` | `const API_BASE = "<YOUR_CLOUD_RUN_URL>";` | Directs client-side AJAX calls to backend. |
| **2. Vercel CSP Header** | `web/vercel.json` | `"connect-src 'self' http://localhost:8080 http://127.0.0.1:8080 <YOUR_CLOUD_RUN_URL>;"` | Strict CSP header allowing browser connections to Cloud Run. |
| **3. Cloud Run Env Var** | Cloud Run Service | `ALLOWED_ORIGINS="<YOUR_VERCEL_URL>"` | CORS Whitelist on Cloud Run. |

---

## 5. Deploy the Static Frontend to Vercel

```bash
# 1. Install Vercel CLI (or link repository in Vercel Dashboard)
npm i -g vercel

# 2. Deploy from repo root
vercel --prod
```

---

## 6. Verification Checklist & Troubleshooting

1. Open your deployed Vercel URL in a browser (e.g., `https://your-app.vercel.app/bias.html`).
2. **Check the Status Indicator**: Look at the top-right status dot next to "API Status".
   - 🟢 **Green**: Connected to backend (`GET /health` returned HTTP 200).
   - 🔘 **Grey**: Disconnected / Error.
3. **Run Analysis**: Click **"Analyze Job Posting"** on `bias.html` and confirm live result card rendering.

### What a Grey Dot Means (Two Things to Check)
1. **CORS Mismatch**: Verify that `ALLOWED_ORIGINS` on Cloud Run matches your exact Vercel origin (`https://your-app.vercel.app`).
2. **API Base Mismatch**: Verify that `API_BASE` in `web/assets/site.js` and `connect-src` in `web/vercel.json` match your Cloud Run URL (`https://governance-api-abc123xyz-el.a.run.app`).
