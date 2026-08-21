# HearBeat Backend - GCP Deployment Guide

This guide covers deploying the HearBeat analysis backend to Google Cloud Platform.

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- A GCP project created
- Docker installed locally (for building)

## Quick Deploy (Cloud Run - Recommended)

Cloud Run is the simplest option: serverless, auto-scales, handles traffic spikes, and you only pay for actual usage.

### 1. Set project

```bash
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID
```

### 2. Enable required APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 3. Build and deploy (one-shot)

```bash
cd backend

# Build container image
gcloud builds submit --tag gcr.io/$PROJECT_ID/hearbeat-api

# Deploy to Cloud Run
gcloud run deploy hearbeat-api \
  --image gcr.io/$PROJECT_ID/hearbeat-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 3 \
  --min-instances 0 \
  --set-env-vars "DEVICE=cpu,DEMUCS_MODEL=htdemucs,MAX_UPLOAD_MB=100"
```

### 4. Get the service URL

```bash
gcloud run services describe hearbeat-api \
  --region us-central1 \
  --format 'value(status.url)'
```

This URL is your `NEXT_PUBLIC_API_URL` for the Vercel frontend.

---

## Manual Docker Build (Alternative)

If you prefer building locally:

```bash
cd backend

# Build
docker build -t hearbeat-api .

# Test locally
docker run -p 8000:8000 \
  -e DEVICE=cpu \
  -e DEMUCS_MODEL=htdemucs \
  hearbeat-api

# Tag and push to GCR
docker tag hearbeat-api gcr.io/$PROJECT_ID/hearbeat-api
docker push gcr.io/$PROJECT_ID/hearbeat-api
```

Then deploy:

```bash
gcloud run deploy hearbeat-api \
  --image gcr.io/$PROJECT_ID/hearbeat-api \
  --region us-central1 \
  --allow-unauthenticated
```

---

## Resource Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| Memory | 4Gi | Audio processing is memory-intensive |
| CPU | 2 | For parallel stem separation + analysis |
| Timeout | 300s | Large files can take minutes |
| Max instances | 3 | Prevents runaway costs |
| Min instances | 0 | Scales to zero when idle |

For GPU-accelerated Demucs (much faster stem separation):

```bash
gcloud run deploy hearbeat-api \
  --image gcr.io/$PROJECT_ID/hearbeat-api \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 8Gi \
  --cpu 4 \
  --gpu 1 \
  --gpu-type nvidia-l4 \
  --timeout 600
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE` | `cpu` | PyTorch device: `cpu`, `cuda`, `mps` |
| `DEMUCS_MODEL` | `htdemucs` | Demucs model for stem separation |
| `MAX_UPLOAD_MB` | `100` | Max upload file size in MB |
| `OUTPUT_DIR` | `/app/outputs` | Temp analysis output directory |
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | Server port |
| `DRIVE_TOKEN_ENCRYPTION_KEY` | — | Base64-encoded 32-byte key for AES-256-GCM token encryption. Generate: `python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"` |
| `GOOGLE_DRIVE_CLIENT_ID` | — | Google OAuth client ID for Drive integration |
| `GOOGLE_DRIVE_CLIENT_SECRET` | — | Google OAuth client secret |
| `FRONTEND_URL` | `http://localhost:3000` | Frontend URL for OAuth redirects (e.g. `https://defusic.vercel.app`) |

---

## Cohesivity Integration

The backend uses Cohesivity for auth and database. Set these as Cloud Run env vars:

```bash
gcloud run services update hearbeat-api \
  --region us-central1 \
  --update-env-vars \
    "COHESIVITY_TENANT_ID=your-tenant-id,\
     COHESIVITY_MANAGEMENT_KEY=coh_man_xxx,\
     COHESIVITY_APPLICATION_KEY=coh_app_xxx"
```

**Important:** Never commit these values. Load them from `.cohesivity` or a secrets manager.

For production, use Google Secret Manager:

```bash
# Create secrets
echo -n "coh_man_xxx" | gcloud secrets create cohesivity-management-key --data-file=-
echo -n "coh_app_xxx" | gcloud secrets create cohesivity-application-key --data-file=-

# Grant access to the Cloud Run service account
gcloud secrets add-iam-policy-binding cohesivity-management-key \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

Then reference secrets in Cloud Run:

```bash
gcloud run deploy hearbeat-api \
  --image gcr.io/$PROJECT_ID/hearbeat-api \
  --region us-central1 \
  --update-secrets="COHESIVITY_MANAGEMENT_KEY=cohesivity-management-key:latest" \
  --update-secrets="COHESIVITY_APPLICATION_KEY=cohesivity-application-key:latest"
```

---

## Health Check

After deployment, verify:

```bash
curl https://your-service-url.run.app/health
# {"status":"ok","version":"0.3.0"}
```

---

## Domain Setup (Optional)

### Custom domain

```bash
gcloud run domain-mappings create \
  --service hearbeat-api \
  --domain api.hearbeat.app \
  --region us-central1
```

### SSL certificate

Cloud Run provisions managed SSL certificates automatically for custom domains.

---

## Monitoring

### Logs

```bash
gcloud run services logs read hearbeat-api --region us-central1 --limit 50
```

### Metrics

View in Cloud Console: Cloud Run > hearbeat-api > Metrics

---

## Cost Estimate

| Scenario | Monthly Cost |
|----------|-------------|
| Development (0-100 requests/day) | ~$0-5 |
| Light usage (100-1000 requests/day) | ~$5-20 |
| Moderate usage (1000-10000 requests/day) | ~$20-100 |

Cloud Run charges per vCPU-second and GiB-second of actual usage. Scales to zero when idle.

---

## Troubleshooting

### Container fails to start

```bash
gcloud run services logs read hearbeat-api --region us-central1 --limit 20
```

Common issues:
- `ffmpeg` not found: ensure the Dockerfile installs it
- Out of memory: increase `--memory`
- Port mismatch: ensure `API_PORT=8000` matches Dockerfile `EXPOSE`

### Analysis timeout

Increase timeout:

```bash
gcloud run deploy hearbeat-api \
  --region us-central1 \
  --timeout 600
```

### Cold start is slow

Set minimum instances to keep one warm:

```bash
gcloud run deploy hearbeat-api \
  --region us-central1 \
  --min-instances 1
```
