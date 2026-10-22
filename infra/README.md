# Infrastructure

Azure deployment for the judging period, with the Azure CLI (Italy North, the same resource
group as the Foundry project). The Foundry resource and its two model deployments (`gtf-fast`,
`gtf-reasoning`) are created by hand beforehand; their settings come from `.env`.

| File | What it does |
|---|---|
| `deploy.sh` | Creates Blob Storage (Entra ID only, no shared keys), Log Analytics + Application Insights, PostgreSQL Flexible B1ms and the Container App (0.25 vCPU / 0.5 GiB, one replica, image from GHCR) with a managed identity: *Storage Blob Data Reader* on the storage account, *Cognitive Services User* on Foundry. `PHASE=infra` / `PHASE=app` run one half. |
| `upload_data.py` | Uploads the demo data: the recorded runs in `data/recorded/` and the public files of their matches. Every name passes the allowlist the API applies at startup (`api/data_sync.py`), so ground truth cannot be uploaded. |
| `post_judging.sh` | After 10 Nov 2026 only: deletes PostgreSQL and lets the app scale to zero. |

Secrets (database password, App Insights connection string) are Container App secrets; the
generated database password is kept between the two phases in `.deploy.secrets` (local,
git-ignored). Resource names (`gtf-*`) date from the project's first name and are kept.

Redeploy after a push to `main`: CI passes, the `image` workflow pushes
`ghcr.io/lorenzogalli-dev/regista:<commit sha>`, then

```sh
az containerapp update -n gtf-app -g <resource group> --image ghcr.io/lorenzogalli-dev/regista:<commit sha>
```
