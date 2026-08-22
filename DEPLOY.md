# Deployment & Configuration Guide

This guide provides a simple step-by-step checklist for deploying the **Governance API** backend to Google Cloud Run and the **web frontend** to Vercel.

---

## 1. Deploy the Backend to Google Cloud Run

Run the following `gcloud` command from the root of the repository to build and deploy the container:

```bash
gcloud run deploy governance-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars GEMINI_API_KEY="<YOUR_GEMINI_API_KEY>",LLM_PROVIDER="gemini",ALLOWED_ORIGINS="<YOUR_VERCEL_URL>",DEBUG="false"
```

> [!IMPORTANT]
> Replace `<YOUR_GEMINI_API_KEY>` with your actual API key.
> In `--set-env-vars ALLOWED_ORIGINS="..."`, put your Vercel frontend URL (e.g., `https://your-site.vercel.app`). Do **NOT** put the Cloud Run URL here!

---

## 2. Retrieve Your Deployed Cloud Run URL

Once deployment completes, `gcloud` will print your Service URL, or you can retrieve it with:

```bash
gcloud run services describe governance-api --region us-central1 --format 'value(status.url)'
```

*Example Output*: `https://governance-api-abc123xyz-uc.a.run.app`

---

## 3. Update Frontend & Environment Configurations (Only 2 Edits Required!)

Thanks to wildcard `*.run.app` support in `web/vercel.json`, you only need to edit **TWO** places:

| Location | File / Settings | Target Value | Description |
| :--- | :--- | :--- | :--- |
| **1. Frontend JS** | `web/assets/site.js` | `const API_BASE = "<YOUR_CLOUD_RUN_URL>";` | Tells the frontend JS where to send backend requests. |
| **2. Cloud Run Env Var** | Cloud Run Service Env | `ALLOWED_ORIGINS="<YOUR_VERCEL_URL>"` | CORS Whitelist on Cloud Run. **(REVERSAL CALLOUT: Cloud Run takes the VERCEL URL, NOT the Cloud Run URL!)** |

> [!CAUTION]
> **Common Pitfall**: Setting `ALLOWED_ORIGINS` to the Cloud Run URL instead of the Vercel URL will cause CORS errors on the frontend!

---

## 4. Deploy the Static Frontend to Vercel

1. Install the Vercel CLI (or connect your GitHub repository in the Vercel Web Console):
   ```bash
   npm i -g vercel
   ```
2. From the root of the repository, deploy the `web/` directory:
   ```bash
   vercel --prod
   ```
3. Set the root directory in Vercel settings to `web/` if prompted.

---

## 5. Verification Checklist

1. Open your deployed Vercel URL in a browser (e.g., `https://your-site.vercel.app/bias.html`).
2. **Check the Status Indicator**: Look at the top-right status dot next to "API Status".
   - 🟢 **Green**: Connected to backend successfully.
   - 🔘 **Grey**: Disconnected / Error.
3. **Run Analysis**: Click **"Analyze Job Posting"** on `bias.html`.
4. Verify that live detection spans appear and the response time badge updates dynamically (confirming a live API result rather than a fallback sample).

---

## 6. Troubleshooting: What a Grey Dot Means

A grey status dot indicates that the browser failed to reach `GET /health` on the backend.

### Check these 2 things:
1. **CORS Mismatch**: Check Cloud Run's `ALLOWED_ORIGINS` env var. It must match your Vercel URL *exactly* (including `https://` and no trailing slash, e.g. `https://your-app.vercel.app`).
2. **API Endpoint Mismatch**: Check `web/assets/site.js`. `API_BASE` must match your Cloud Run URL *exactly* without a trailing slash (e.g. `https://governance-api-abc123xyz-uc.a.run.app`).
