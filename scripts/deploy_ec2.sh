#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
CONTAINER_NAME="${CONTAINER_NAME:-nexusiq}"
APP_PORT="${APP_PORT:-8080}"
IMAGE_URI="${IMAGE_URI:?IMAGE_URI is required, for example 630589800012.dkr.ecr.us-east-1.amazonaws.com/nexusiq-ai:latest}"

GOOGLE_SECRET_ID="${GOOGLE_SECRET_ID:-nexusiq/google-api-key}"
GROQ_SECRET_ID="${GROQ_SECRET_ID:-nexusiq/groq-api-key}"
DATABASE_SECRET_ID="${DATABASE_SECRET_ID:-nexusiq/database-url}"
PILOT_PDF_VOLUME="${PILOT_PDF_VOLUME:-nexusiq-pilot-pdfs}"
PILOT_CHROMA_VOLUME="${PILOT_CHROMA_VOLUME:-nexusiq-pilot-chroma}"
PILOT_PDF_DIRECTORY="/app/data/pdfs_staging/enterprise_pilot_v1/validated_v2/01_financial"
PILOT_CHROMA_DIRECTORY="/app/data/chroma_staging/enterprise_pilot_v1/validated_v2/financial_documents"

REGISTRY="${IMAGE_URI%%/*}"

volume_path_exists() {
  local volume_name="$1"
  local mount_path="$2"
  local expected_path="$3"
  docker run --rm \
    --mount "type=volume,src=${volume_name},dst=${mount_path}" \
    "${IMAGE_URI}" test -d "${expected_path}"
}

provision_pilot_evidence() {
  echo "Preparing isolated Enterprise Pilot evidence volumes"
  docker volume create "${PILOT_PDF_VOLUME}" >/dev/null
  docker volume create "${PILOT_CHROMA_VOLUME}" >/dev/null

  if volume_path_exists "${PILOT_CHROMA_VOLUME}" "/app/data/chroma_staging" "${PILOT_CHROMA_DIRECTORY}"; then
    echo "Existing isolated pilot index found; validating before deployment"
  elif volume_path_exists "${PILOT_PDF_VOLUME}" "/app/data/pdfs_staging" "${PILOT_PDF_DIRECTORY}"; then
    echo "Pilot PDF volume exists without its validated index; refusing automatic overwrite"
    return 1
  else
    echo "Generating five staging-only pilot PDFs"
    docker run --rm \
      --memory=1800m \
      --mount "type=volume,src=${PILOT_PDF_VOLUME},dst=/app/data/pdfs_staging" \
      -e DATABASE_URL="${DATABASE_URL}" \
      "${IMAGE_URI}" \
      python -m database.generate_pilot_financial_pdfs generate \
        --execute \
        --confirm-staging-only GENERATE_PILOT_PDFS_FROM_STAGING_ONLY

    echo "Building isolated pilot Chroma index after PDF-to-SQL validation"
    docker run --rm \
      --memory=1800m \
      --mount "type=volume,src=${PILOT_PDF_VOLUME},dst=/app/data/pdfs_staging" \
      --mount "type=volume,src=${PILOT_CHROMA_VOLUME},dst=/app/data/chroma_staging" \
      -e DATABASE_URL="${DATABASE_URL}" \
      "${IMAGE_URI}" \
      python -m database.pilot_document_phase ingest \
        --execute \
        --confirm-staging-only INGEST_PILOT_PDFS_TO_ISOLATED_STAGING_ONLY \
        --confirm-pdf-validation VALIDATE_PILOT_PDFS_AGAINST_STAGING_SQL_ONLY
  fi

  echo "Validating staged PDF facts against Supabase staging SQL"
  docker run --rm \
    --memory=1800m \
    --mount "type=volume,src=${PILOT_PDF_VOLUME},dst=/app/data/pdfs_staging" \
    -e DATABASE_URL="${DATABASE_URL}" \
    "${IMAGE_URI}" \
    python -m database.pilot_document_phase validate-alignment \
      --execute-remote \
      --confirm-staging-only VALIDATE_PILOT_PDFS_AGAINST_STAGING_SQL_ONLY

  echo "Validating isolated pilot index against Supabase staging SQL"
  docker run --rm \
    --memory=1800m \
    --mount "type=volume,src=${PILOT_CHROMA_VOLUME},dst=/app/data/chroma_staging" \
    -e DATABASE_URL="${DATABASE_URL}" \
    "${IMAGE_URI}" \
    python -m database.pilot_document_phase validate-index-alignment \
      --execute-remote \
      --confirm-staging-only VALIDATE_PILOT_STAGING_INDEX_AGAINST_STAGING_SQL_ONLY
}

echo "Logging in to ECR registry: ${REGISTRY}"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}" >/dev/null

echo "Reclaiming unused Docker storage before image pull"
docker system df || true
# This preserves images referenced by the currently running application container.
docker system prune --all --force || true
docker system df || true

echo "Pulling image: ${IMAGE_URI}"
docker pull "${IMAGE_URI}"

echo "Reading runtime secrets from AWS Secrets Manager"
GOOGLE_API_KEY="$(aws secretsmanager get-secret-value --secret-id "${GOOGLE_SECRET_ID}" --query SecretString --output text --region "${AWS_REGION}")"
GROQ_API_KEY="$(aws secretsmanager get-secret-value --secret-id "${GROQ_SECRET_ID}" --query SecretString --output text --region "${AWS_REGION}")"
DATABASE_URL="$(aws secretsmanager get-secret-value --secret-id "${DATABASE_SECRET_ID}" --query SecretString --output text --region "${AWS_REGION}")"

provision_pilot_evidence

echo "Replacing container: ${CONTAINER_NAME}"
docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
docker rm "${CONTAINER_NAME}" >/dev/null 2>&1 || true

docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  --memory=1800m \
  -p "${APP_PORT}:8080" \
  --mount "type=volume,src=${PILOT_PDF_VOLUME},dst=/app/data/pdfs_staging" \
  --mount "type=volume,src=${PILOT_CHROMA_VOLUME},dst=/app/data/chroma_staging" \
  -e PORT=8080 \
  -e ENVIRONMENT=production \
  -e AWS_REGION="${AWS_REGION}" \
  -e GOOGLE_API_KEY="${GOOGLE_API_KEY}" \
  -e GROQ_API_KEY="${GROQ_API_KEY}" \
  -e DATABASE_URL="${DATABASE_URL}" \
  "${IMAGE_URI}"

echo "Pruning previous unused image layers after replacement"
docker image prune --all --force || true

echo "Waiting for app to become reachable on localhost:${APP_PORT}"
for attempt in {1..30}; do
  if curl -fsS "http://localhost:${APP_PORT}" >/dev/null; then
    echo "Health check passed"
    docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
    exit 0
  fi
  echo "Attempt ${attempt}/30: app not ready yet"
  sleep 2
done

echo "Container logs:"
docker logs --tail 120 "${CONTAINER_NAME}" || true
echo "Health check failed: http://localhost:${APP_PORT} did not respond"
exit 1
