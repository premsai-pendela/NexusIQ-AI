# Deploy NexusIQ AI to Google Cloud Run

This is the low-risk Track A deployment path: containerize the existing Streamlit app and keep the current Postgres + committed ChromaDB baseline.

## 1. Build Locally

```bash
docker build -t nexusiq-ai .
docker run --rm -p 8080:8080 \
  --env-file .env \
  -e PORT=8080 \
  nexusiq-ai
```

Open `http://localhost:8080` and test:

```text
Validate Q4 Electronics revenue across SQL and PDF reports.
What are Q4 2024 strategic priorities?
What are competitor prices for electronics?
```

## 2. Create GCP Resources

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com
gcloud artifacts repositories create nexusiq \
  --repository-format=docker \
  --location=us-central1
```

## 3. Store Secrets

Create these secrets in Secret Manager:

```bash
printf '%s' 'YOUR_GOOGLE_KEY' | gcloud secrets create GOOGLE_API_KEY --data-file=-
printf '%s' 'YOUR_GROQ_KEY' | gcloud secrets create GROQ_API_KEY --data-file=-
printf '%s' 'YOUR_DATABASE_URL' | gcloud secrets create DATABASE_URL --data-file=-
```

Grant the Cloud Run service account secret access before deploy.

## 4. Build And Push

```bash
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/nexusiq/nexusiq-ai:latest
```

## 5. Deploy

```bash
gcloud run deploy nexusiq-ai \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/nexusiq/nexusiq-ai:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --concurrency 1 \
  --max-instances 1 \
  --set-env-vars ENVIRONMENT=production,CHROMA_PERSIST_DIRECTORY=./data/chroma_db \
  --set-secrets GOOGLE_API_KEY=GOOGLE_API_KEY:latest,GROQ_API_KEY=GROQ_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest
```

Use `--min-instances 1` only when you are actively demoing and want to avoid cold starts.

## Notes

- Do not migrate ChromaDB to pgvector in the first Cloud Run deployment. Preserve current behavior first.
- Selenium-based scraping is not part of the Cloud Run baseline. API/BeautifulSoup scrapers should remain available.
- Keep `.env` local only. Cloud Run should receive secrets through Secret Manager.
