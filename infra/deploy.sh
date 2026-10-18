#!/usr/bin/env bash
# Hosting for the judging period (profile A): one Container App (0.25 vCPU / 0.5 GiB, one
# replica always on), PostgreSQL Flexible B1ms, Blob Storage for the demo data, Application
# Insights. Region Italy North, same resource group as the Foundry project.
#
#   infra/deploy.sh <image-tag>          e.g. infra/deploy.sh 02375f8...
#   PHASE=infra infra/deploy.sh -        everything except the Container App
#   PHASE=app infra/deploy.sh <tag>      only the Container App, on existing infrastructure
#
# Needs: az login, the containerapp extension, the Foundry settings in .env. Secrets (database
# password, App Insights connection string) go into Container App secrets, never into the repo.
set -euo pipefail

RG=${RG:-rg-lgalli-1289}
LOC=${LOC:-italynorth}
SUFFIX=${SUFFIX:-gtf0893}
STORAGE=${STORAGE:-${SUFFIX}data}
CONTAINER=gtf-data
LOGS=gtf-logs
INSIGHTS=gtf-insights
PG=${PG:-${SUFFIX}-pg}
ENVNAME=gtf-env
APP=gtf-app
FOUNDRY=${FOUNDRY:-gtf-foundry}
IMAGE=ghcr.io/lorenzogalli-dev/regista:${1:?image tag, or - with PHASE=infra}
set -a; source .env; set +a

if [[ "${PHASE:-all}" != app ]]; then
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.Insights Microsoft.DBforPostgreSQL Microsoft.Storage; do
  az provider register --namespace "$ns" --wait --only-show-errors
done

# --- Blob Storage: private, Entra ID only (no shared keys) --------------------------------
az storage account create -g "$RG" -n "$STORAGE" -l "$LOC" --sku Standard_LRS --kind StorageV2 \
  --allow-blob-public-access false --allow-shared-key-access false --min-tls-version TLS1_2 -o none
STORAGE_ID=$(az storage account show -g "$RG" -n "$STORAGE" --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --assignee "$ME" --role "Storage Blob Data Contributor" --scope "$STORAGE_ID" -o none || true
az storage container create --account-name "$STORAGE" -n "$CONTAINER" --auth-mode login -o none
uv run python infra/upload_data.py "$STORAGE" "$CONTAINER"

# --- Monitoring ----------------------------------------------------------------------------
az monitor log-analytics workspace create -g "$RG" -n "$LOGS" -l "$LOC" -o none
LOGS_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LOGS" --query customerId -o tsv)
LOGS_KEY=$(az monitor log-analytics workspace get-shared-keys -g "$RG" -n "$LOGS" --query primarySharedKey -o tsv)
az monitor app-insights component create -g "$RG" -a "$INSIGHTS" -l "$LOC" --workspace "$LOGS" -o none
AI_CS=$(az monitor app-insights component show -g "$RG" -a "$INSIGHTS" --query connectionString -o tsv)

# --- PostgreSQL Flexible, smallest Burstable -------------------------------------------------
PG_PASS=${PG_PASS:-$(openssl rand -base64 30 | tr -dc 'A-Za-z0-9' | head -c 28)}
az postgres flexible-server create -g "$RG" -n "$PG" -l "$LOC" --tier Burstable --sku-name Standard_B1ms \
  --storage-size 32 --version 17 --admin-user gtfadmin --admin-password "$PG_PASS" \
  --public-access 0.0.0.0 --yes -o none
az postgres flexible-server db create --resource-group "$RG" --server-name "$PG" --name gtf -o none
fi  # end of infrastructure

if [[ "${PHASE:-all}" == app ]]; then
  source .deploy.secrets  # PG_PASS from the infra phase
  STORAGE_ID=$(az storage account show -g "$RG" -n "$STORAGE" --query id -o tsv)
  LOGS_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LOGS" --query customerId -o tsv)
  LOGS_KEY=$(az monitor log-analytics workspace get-shared-keys -g "$RG" -n "$LOGS" --query primarySharedKey -o tsv)
  AI_CS=$(az monitor app-insights component show -g "$RG" -a "$INSIGHTS" --query connectionString -o tsv)
fi
DATABASE_URL="postgresql://gtfadmin:${PG_PASS}@${PG}.postgres.database.azure.com:5432/gtf?sslmode=require"

# --- Container App ---------------------------------------------------------------------------
[[ "${PHASE:-all}" == app ]] || az containerapp env create -g "$RG" -n "$ENVNAME" -l "$LOC" \
  --logs-workspace-id "$LOGS_ID" --logs-workspace-key "$LOGS_KEY" -o none
if [[ "${PHASE:-all}" == infra ]]; then
  # Keep the generated database password for the second phase (local file, git-ignored).
  printf 'PG_PASS=%s\n' "$PG_PASS" > .deploy.secrets
  echo "infra ready; run again without PHASE (with PG_PASS from .deploy.secrets) to create the app"
  exit 0
fi
az containerapp create -g "$RG" -n "$APP" --environment "$ENVNAME" --image "$IMAGE" \
  --cpu 0.25 --memory 0.5Gi --min-replicas 1 --max-replicas 1 \
  --ingress external --target-port 8000 --system-assigned \
  --secrets "database-url=$DATABASE_URL" "appinsights=$AI_CS" \
  --env-vars "DATABASE_URL=secretref:database-url" "APPLICATIONINSIGHTS_CONNECTION_STRING=secretref:appinsights" \
    "DATA_BLOB_URL=https://${STORAGE}.blob.core.windows.net/${CONTAINER}" \
    "MATCH_DATA_DIR=/app/data/generated" "RUNS_DIR=/app/data/recorded" \
    "MODEL_PROVIDER=foundry" "FOUNDRY_PROJECT_ENDPOINT=$FOUNDRY_PROJECT_ENDPOINT" \
    "FOUNDRY_MODEL_FAST=$FOUNDRY_MODEL_FAST" "FOUNDRY_MODEL_REASONING=$FOUNDRY_MODEL_REASONING" \
    "FOUNDRY_REASONING_EFFORT=low" "LIVE_DAILY_MODEL_CALL_CAP=${LIVE_CAP:-150}" -o none
FQDN=$(az containerapp show -g "$RG" -n "$APP" --query properties.configuration.ingress.fqdn -o tsv)
az containerapp update -g "$RG" -n "$APP" --set-env-vars "MCP_ALLOWED_HOSTS=localhost:*,127.0.0.1:*,${FQDN},${FQDN}:*" -o none

# The app's identity may read the blobs and call the Foundry models (live sessions); nothing else.
PRINCIPAL=$(az containerapp show -g "$RG" -n "$APP" --query identity.principalId -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Reader" --scope "$STORAGE_ID" -o none
FOUNDRY_ID=$(az cognitiveservices account show -g "$RG" -n "$FOUNDRY" --query id -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services User" --scope "$FOUNDRY_ID" -o none
az containerapp revision restart -g "$RG" -n "$APP" \
  --revision "$(az containerapp show -g "$RG" -n "$APP" --query properties.latestRevisionName -o tsv)" -o none

echo "https://${FQDN}"
