# NexusIQ AWS Migration Plan
## Status: EC2 deploy live — custom domain + CI/CD complete, RDS pending

Last updated: 2026-05-22

---

## DEPLOYMENT ARCHITECTURE (decided)

```
AWS EC2 t3.small (2GB RAM, ~$15/mo covered by $100 AWS credits)
    │  ← runs Streamlit container on :8080
    │  ← Caddy terminates HTTPS for nexusiq-ai.com
    ├──→ Supabase PostgreSQL (current DATABASE_URL secret)
    ├──→ AWS S3 (PDF archive uploaded)
    └──→ AWS ECR (Docker image)

Single-cloud: everything on AWS
Resume story: "Deployed on AWS — EC2, S3, ECR, Secrets Manager, CloudWatch; RDS migration is the remaining database step"
```

**AWS account type:** AWS Educate/Activate — $100 credits, expires 19 Nov 2026.
**Cost:** EC2 t3.small ~$15/mo + RDS ~$13/mo = ~$28/mo → $100 covers ~3.5 months.
  If RDS free tier applies → $15/mo → $100 covers 6+ months.
**Azure:** NOT needed. Dropped from plan.
**Streamlit Cloud:** stays live as backup. AWS = primary.
**wake_up.yml:** keep as-is (still pings Streamlit Cloud backup).
**Public URL:** `https://nexusiq-ai.com`

---

## PHASE STATUS

### ✅ PHASE 0 — Security (COMPLETE)
- [x] Rotated Supabase DB password
- [x] Rotated Gemini API key
- [x] Rotated Groq API key
- [x] Confirmed `generate_financial_pdfs.py` uses env var (not hardcoded)
- NOTE: old credential exists in git commit `a4fa4dd` — repo must stay private or credential is dead (rotated)

---

### 🟨 PHASE 1 — Account Setup (MOSTLY COMPLETE)
- [x] AWS account configured in `us-east-1`
- [ ] Set billing alert at $5 and $20
- [x] Enable services: ECR, S3, Secrets Manager, CloudWatch
- [ ] Enable RDS when ready to migrate off Supabase
- [x] Create IAM user `Nexusiq_AI-Deploy`
- [x] Install AWS CLI and configure local deploy credentials
- [ ] Verify $100 credits in AWS console: Billing → Credits
- [ ] Redeem LocalStack pro license from GitHub Student Pack (for local dev)
- NOTE: Azure no longer needed — dropped from plan

---

### ✅ PHASE 2 — Code Fixes for Cloud (COMPLETE)

All fixes done together before Docker build:

**`requirements.txt`:**
- [x] Remove `torchvision>=0.16.0` (never imported, saves image weight)
- [x] Add CPU-only PyTorch extra index

**`agents/web_agent.py`:**
- [x] Replace `_scrape_ikea_selenium()` with IKEA internal JSON API
  - Endpoint: `https://sik.search.blue.cdtapps.com/us/en/search-result-page`
  - Use `httpx` (already in requirements) — no browser needed
  - Zero Docker changes, cloud-safe, faster than Selenium
  - Remove Firefox/GeckoDriver from Dockerfile entirely

**`config/settings.py`:**
- [x] Keep `environment: str = "development"`
- [x] Add `ENVIRONMENT=production` to EC2 container env vars

**`database/generate_financial_pdfs.py`:**
- [x] Line 22 already clean (env var). Confirmed during security pass.

---

### ✅ PHASE 3 — Docker Build + Local/Production Test (COMPLETE)

```bash
# Build locally (chroma_db files exist locally — NOT in git clone)
docker build -t nexusiq-ai .
docker run -p 8080:8080 \
  -e GOOGLE_API_KEY=... \
  -e GROQ_API_KEY=... \
  -e DATABASE_URL=... \
  -e ENVIRONMENT=production \
  nexusiq-ai

# Verify all agents work:
# - SQL Agent query
# - RAG Agent query
# - Web Agent (IKEA API + Shopify + BS4)
# - Fusion Agent multi-source
```

**ChromaDB note:** Build image LOCALLY (not CI/CD) so local chroma_db files are bundled.
Docker COPY includes data/chroma_db/ because .dockerignore only excludes data/chroma_db_local/.
3 of 4 chroma collections are local-only (not in git) — must build from working directory.

Verification on 2026-05-20:
- Built `linux/amd64` image for EC2.
- Pushed ECR digest `sha256:29e5fccd42a2ac00cb109060c43ec3ca1c4b430611460b355a2f950c465c3238`.
- EC2 production query returned Q4 2024 Electronics revenue `$31,710,925.89`.
- RAG retrieved `01_Q4_2024_Financial_Report.pdf`; SQL/RAG validation was HIGH.

---

### 🟨 PHASE 4 — AWS Setup (MOSTLY COMPLETE, RDS PENDING)

```bash
# Create ECR repository
aws ecr create-repository --repository-name nexusiq-ai --region us-east-1

# Push image to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker tag nexusiq-ai:latest <account>.dkr.ecr.us-east-1.amazonaws.com/nexusiq-ai:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/nexusiq-ai:latest
```

**RDS Setup:**
```bash
# Free tier: db.t3.micro, PostgreSQL 15, 20GB gp2
# Enable pgvector extension (for Track B later)
# Migrate from Supabase: pg_dump → pg_restore
```

Current status:
- No RDS instance exists in `us-east-1`.
- `nexusiq/database-url` currently points to Supabase host `aws-1-us-east-2.pooler.supabase.com`.
- Leave RDS creation as an explicit cost/architecture decision.

**S3 Setup:**
```bash
aws s3 mb s3://nexusiq-pdfs-<accountid>
aws s3 sync data/pdfs/ s3://nexusiq-pdfs-<accountid>/
```

Current status:
- Bucket `nexusiq-pdfs-630589800012` exists.
- 25 PDFs uploaded on 2026-05-20.

**Secrets Manager:**
```bash
aws secretsmanager create-secret --name nexusiq/google-api-key --secret-string "..."
aws secretsmanager create-secret --name nexusiq/groq-api-key --secret-string "..."
aws secretsmanager create-secret --name nexusiq/database-url --secret-string "postgresql://..."
```

Current status:
- `nexusiq/google-api-key`, `nexusiq/groq-api-key`, and `nexusiq/database-url` exist.

---

### ✅ PHASE 5 — EC2 Deploy (COMPLETE 2026-05-20)

Stable Elastic IP:

```text
52.3.111.212
```

```bash
# Launch EC2 t3.small (2GB RAM, Ubuntu 22.04, 20GB EBS)
# Open port 8080 in security group
# Attach IAM role with ECR pull + Secrets Manager read permissions

# On EC2:
sudo apt update && sudo apt install docker.io -y
sudo systemctl start docker
sudo usermod -aG docker ubuntu

# Pull from ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker pull <account>.dkr.ecr.us-east-1.amazonaws.com/nexusiq-ai:latest

# Run container
docker run -d --restart=always \
  --name nexusiq \
  -p 8080:8080 \
  --memory=1800m \
  -e GOOGLE_API_KEY=$(aws secretsmanager get-secret-value --secret-id nexusiq/google-api-key --query SecretString --output text) \
  -e GROQ_API_KEY=$(aws secretsmanager get-secret-value --secret-id nexusiq/groq-api-key --query SecretString --output text) \
  -e DATABASE_URL=$(aws secretsmanager get-secret-value --secret-id nexusiq/database-url --query SecretString --output text) \
  -e ENVIRONMENT=production \
  <account>.dkr.ecr.us-east-1.amazonaws.com/nexusiq-ai:latest
```

Note: t3.small = 2GB RAM. No swap needed. No OOM risk.

---

### 🟨 PHASE 6 — Observability + Health Check (FOUNDATION COMPLETE)

- [x] Add CloudWatch log group `/nexusiq/traces`
- [x] Update `observability/tracer.py` to optionally write to CloudWatch when `ENVIRONMENT=production`
- [x] Public health check now targets `https://nexusiq-ai.com`
- [x] Raw public `:8080` access closed; Streamlit remains reachable internally through Caddy

---

### ✅ PHASE 7 — CI/CD (GitHub Actions)

```yaml
# On push to main:
# 1. Build Docker image locally (or in Actions with S3-cached chroma_db)
# 2. Push to ECR
# 3. SSH to EC2, pull new image, restart container
```

Current status:
- `.github/workflows/deploy-ec2.yml` builds the Docker image on push to `main`.
- The workflow pushes `latest` to ECR.
- The workflow copies `scripts/deploy_ec2.sh` to EC2 over SSH.
- EC2 pulls the new image, provisions or revalidates isolated Enterprise Pilot
  PDF/RAG evidence in persistent Docker volumes, restarts the `nexusiq`
  container with those volumes mounted, and runs a public health check.

Note: Track B (pgvector/S3 ingestion) still eliminates the long-term need to bundle ChromaDB in the image.

---

### ✅ PHASE 8 — Custom Domain + HTTPS (COMPLETE 2026-05-22)

- Elastic IP attached: `52.3.111.212`
- Cloudflare DNS points `nexusiq-ai.com` to the Elastic IP.
- Caddy is installed on EC2.
- Caddy provides HTTPS reverse proxy from `https://nexusiq-ai.com` to Streamlit on port `8080`.
- EC2 security group now exposes only public web ports `80`/`443` plus SSH; raw public `8080` was removed after HTTPS health checks were stable.
- Public demo formatting was polished after deployment:
  - `3803d23` — stabilize public validation answer.
  - `6598a77` — escape currency in Streamlit markdown.

---

## TRACK B — RAG Modernization (after Track A stable)

Do AFTER app working on cloud:

1. Add `document_chunks` table to RDS with `vector(384)` column (pgvector)
2. Write ChromaDB → pgvector migration script
3. Add retrieval adapter in `rag_agent.py` with `USE_PGVECTOR=true` flag
4. Test RAG answer parity against golden eval cases
5. Replace BM25 with Postgres full-text search OR keep BM25 in-memory
6. S3 event → Lambda/ECS Job for ingestion pipeline automation

---

## RISK REGISTER (post-loop, all mitigated)

| Risk | Mitigation | Status |
|------|-----------|--------|
| Hardcoded credential | Rotated all keys | ✅ DONE |
| ChromaDB ephemeral wipe | Build image locally with bundled ChromaDB; Track B moves retrieval to pgvector/S3 | ✅ Handled for Track A |
| Selenium no display on server | Replace with IKEA JSON API | ✅ Phase 2 |
| t2.micro OOM | EC2 t3.small with 2GB RAM | ✅ Handled |
| torchvision unnecessary weight | Remove from requirements.txt | ✅ Phase 2 |
| ChromaDB not in git for CI/CD | Build image locally for now | ✅ Documented |
| wake_up.yml pinging Streamlit Cloud | Keep — Streamlit Cloud stays as backup | ✅ Intentional |

---

## RESUME STORY (final)

> "Deployed NexusIQ on AWS — EC2 t3.small for the containerized Streamlit app, ECR for the image registry, S3 for document archive storage, Secrets Manager for credentials, and CloudWatch for production traces. Replaced brittle Selenium scraping with direct IKEA API integration for cloud-native reliability. The current database secret still points to Supabase; RDS migration is the remaining Phase 4 database step."

AWS services touched: EC2, S3, ECR, Secrets Manager, CloudWatch

---

## NEXT SESSION CHECKLIST

Start here:
1. Update README/resume-facing documentation with the live URL and AWS architecture story.
2. Add CloudWatch dashboard/alarms for uptime, container errors, and slow traces.
3. Decide whether to restrict SSH from `0.0.0.0/0` to a trusted IP range.
4. Decide whether to create RDS now or keep Supabase through the demo.
5. Later: Track B can move RAG chunks from bundled ChromaDB to pgvector/S3 ingestion.

Questions resolved:
- ✅ Streamlit Cloud: keep as backup
- ✅ IKEA scraping: replace Selenium with IKEA JSON API
- ✅ Compute: AWS EC2 t3.small
- ✅ Single-cloud direction: AWS primary, Streamlit Cloud backup
- ✅ Custom domain: Cloudflare + Caddy HTTPS
- ✅ CI/CD: GitHub Actions to ECR + EC2
- ✅ Security tightening: raw public `:8080` closed
