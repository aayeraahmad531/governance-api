# Deployment Guide — Hugging Face Spaces + Vercel

This guide provides a step-by-step checklist to deploy the **AI Governance API** backend to Hugging Face Spaces (Docker SDK, Free CPU) and the frontend site to Vercel.

---

## Overview & Architecture

- **Backend**: Containerized FastAPI service running on Hugging Face Spaces (Port 7860, Docker SDK, Free CPU, no credit card required).
- **Frontend**: Static 4-page UI (`web/`) deployed on Vercel.
- **Backend API Base URL**: `https://<YOUR_HF_USERNAME>-<YOUR_SPACE_NAME>.hf.space`
- **Frontend URL**: `https://<YOUR_VERCEL_APP>.vercel.app`

---

## Step 1: Create Hugging Face Space (Browser Step)

1. Open your browser and log in to [Hugging Face](https://huggingface.co/).
2. Navigate to **New Space** ([https://huggingface.co/new-space](https://huggingface.co/new-space)).
3. Configure the Space settings:
   - **Space Name**: `ai-governance-api` (or your preferred name)
   - **License**: `mit`
   - **Select the Space SDK**: **Docker** $\rightarrow$ **Blank**
   - **Space Hardware**: **CPU Basic (2 vCPU · 16 GB - Free)**
   - **Privacy**: **Public**
4. Click **Create Space**.

---

## Step 2: Configure Environment Variables & Secrets in Hugging Face (Browser Step)

1. On your newly created Space page, click on **Settings** (top right tab).
2. Scroll down to **Variables and secrets**.
3. Add your secret key:
   - Click **New secret**.
   - **Name**: `GEMINI_API_KEY`
   - **Value**: `<YOUR_GEMINI_API_KEY>` (paste your key from local `.env`)
   - Click **Save**.
4. Add environment variables:
   - Click **New variable**.
   - **Name**: `LLM_PROVIDER`
   - **Value**: `gemini`
   - Click **Save**.
   - Click **New variable**.
   - **Name**: `DEBUG`
   - **Value**: `false`
   - Click **Save**.
   - Click **New variable**.
   - **Name**: `ALLOWED_ORIGINS`
   - **Value**: `https://<YOUR_VERCEL_APP>.vercel.app` (**REVERSAL REMINDER**: This takes your **Vercel Frontend URL**, NOT the Hugging Face URL!).
   - Click **Save**.

---

## Step 3: Push Code to Hugging Face Space Remote

Run the following commands in your local terminal:

```bash
# 1. Add your Hugging Face Space as a git remote
git remote add hf https://huggingface.co/spaces/<YOUR_HF_USERNAME>/<YOUR_SPACE_NAME>

# 2. Push the code to build and start the Space container
git push hf main:main
```

Once pushed, Hugging Face will automatically execute `Dockerfile` and start the container on port `7860`.

---

## Step 4: Synchronize URLs Across Configuration Files

You must update the deployed backend URL in exactly **THREE** places:

1. **`web/assets/site.js`** (Line 5):
   ```javascript
   const API_BASE = "https://<YOUR_HF_USERNAME>-<YOUR_SPACE_NAME>.hf.space";
   ```
2. **`web/vercel.json`** (Line 16 - `connect-src` CSP Header):
   ```json
   "value": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self' http://localhost:7860 http://127.0.0.1:7860 https://<YOUR_HF_USERNAME>-<YOUR_SPACE_NAME>.hf.space;"
   ```
3. **Hugging Face Space Settings** (`ALLOWED_ORIGINS` variable):
   - Set `ALLOWED_ORIGINS` to your Vercel URL (`https://<YOUR_VERCEL_APP>.vercel.app`).
   - **Reversal Reminder**: Hugging Face configuration takes your **Vercel URL**; Vercel CSP configuration takes your **Hugging Face URL**.

---

## Step 5: Deploy Frontend to Vercel

```bash
# Deploy static web/ directory to Vercel
npx vercel --prod
```

---

## Step 6: Verify End-to-End Operation

1. Open your deployed Vercel site in a browser (e.g. `https://<YOUR_VERCEL_APP>.vercel.app/bias.html`).
2. Verify the **status dot** in the UI console header is **GREEN** (indicating `live` connection to Hugging Face Space) rather than grey (`cached`).
3. Click **Run audit** on `bias.html`.
4. Confirm a real audit result is rendered with highlighted spans and category risk scores.

### Troubleshooting Status Indicators
- **Grey Dot (`cached`)**:
  - The `API_BASE` in `web/assets/site.js` is still `null` or pointing to `localhost`.
  - The Hugging Face Space is currently sleeping (free Spaces sleep after inactivity). The frontend auto-pings `/health` to wake it up; wait 15–30 seconds for container startup.
- **Red CORS Error in Console**:
  - `ALLOWED_ORIGINS` in Hugging Face Space Settings does not match the exact Vercel origin. Check for typos or trailing slashes.
