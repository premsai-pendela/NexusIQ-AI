#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
CONTAINER_NAME="${CONTAINER_NAME:-nexusiq}"
APP_PORT="${APP_PORT:-8080}"
IMAGE_URI="${IMAGE_URI:?IMAGE_URI is required, for example 630589800012.dkr.ecr.us-east-1.amazonaws.com/nexusiq-ai:latest}"

GOOGLE_SECRET_ID="${GOOGLE_SECRET_ID:-nexusiq/google-api-key}"
GROQ_SECRET_ID="${GROQ_SECRET_ID:-nexusiq/groq-api-key}"
DATABASE_SECRET_ID="${DATABASE_SECRET_ID:-nexusiq/database-url}"

REGISTRY="${IMAGE_URI%%/*}"

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

echo "Replacing container: ${CONTAINER_NAME}"
docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
docker rm "${CONTAINER_NAME}" >/dev/null 2>&1 || true

docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  --memory=1800m \
  -p "${APP_PORT}:8080" \
  -p 8000:8000 \
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
