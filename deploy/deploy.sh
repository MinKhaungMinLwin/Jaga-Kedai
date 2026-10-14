#!/usr/bin/env bash
# Deploy Jaga Kedai: Firestore + Cloud Run API (Gemini on Vertex AI) + Firebase Hosting.
#
#   PROJECT_ID=my-project deploy/deploy.sh
#
# Optional: MODEL, REGION, ADMIN_TOKEN, PHOENIX_COLLECTOR_ENDPOINT, PHOENIX_API_KEY, MIN_INSTANCES.
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID}"
REGION="${REGION:-asia-southeast1}"
MODEL="${MODEL:-gemini-3.5-flash-lite}"
SERVICE="jaga-kedai-api"
SA_NAME="jaga-kedai-api"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
MIN_INSTANCES="${MIN_INSTANCES:-1}"   # stays warm through judging; set 0 afterwards to save cost

step() { printf '\n\033[1;31m==> %s\033[0m\n' "$*"; }
exists() { "$@" >/dev/null 2>&1; }
cd "$(dirname "$0")/.."

step "Enabling APIs"
gcloud services enable run.googleapis.com firestore.googleapis.com aiplatform.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com firebase.googleapis.com \
  firebasehosting.googleapis.com iam.googleapis.com --project "$PROJECT_ID"

step "Firestore (Native mode, ${REGION})"
exists gcloud firestore databases describe --database="(default)" --project "$PROJECT_ID" ||
  gcloud firestore databases create --location="$REGION" --type=firestore-native --project "$PROJECT_ID"

step "Service account with least-privilege roles"
exists gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" ||
  gcloud iam service-accounts create "$SA_NAME" --display-name "Jaga Kedai API" --project "$PROJECT_ID"
for role in roles/datastore.user roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:${SA}" --role "$role" \
    --condition=None >/dev/null
done

step "Build account roles (new projects no longer grant these automatically)"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format 'value(projectNumber)')"
BUILD_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for role in roles/run.builder roles/logging.logWriter roles/artifactregistry.writer roles/storage.objectViewer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:${BUILD_SA}" --role "$role" \
    --condition=None >/dev/null
done

ENV_VARS="^|^KEDAI_STORE=firestore|KEDAI_AI_BACKEND=vertex|GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
ENV_VARS+="|GOOGLE_CLOUD_LOCATION=global|KEDAI_MODEL=${MODEL}"
[[ -n "${ADMIN_TOKEN:-}" ]] && ENV_VARS+="|KEDAI_ADMIN_TOKEN=${ADMIN_TOKEN}"
if [[ -n "${PHOENIX_COLLECTOR_ENDPOINT:-}" ]]; then
  ENV_VARS+="|PHOENIX_COLLECTOR_ENDPOINT=${PHOENIX_COLLECTOR_ENDPOINT}|PHOENIX_API_KEY=${PHOENIX_API_KEY:-}"
fi

step "Cloud Run API (built by Cloud Build from api/Dockerfile)"
gcloud run deploy "$SERVICE" --source api --region "$REGION" --project "$PROJECT_ID" \
  --service-account "$SA" --allow-unauthenticated --set-env-vars "$ENV_VARS" \
  --cpu 1 --memory 512Mi --timeout 60 --min-instances "$MIN_INSTANCES" --max-instances 5
API_URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')"
curl -sf "${API_URL}/api/today" >/dev/null && echo "API is serving the demo shop."

step "Firebase Hosting + Firestore rules"
firebase projects:addfirebase "$PROJECT_ID" >/dev/null 2>&1 || true
(cd web && npm ci --no-audit --no-fund && npm run build)
firebase deploy --only hosting,firestore:rules --project "$PROJECT_ID" --non-interactive

cat <<DONE

Jaga Kedai is live:
  App: https://${PROJECT_ID}.web.app
  API: ${API_URL}/api/health
DONE
