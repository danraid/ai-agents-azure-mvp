# Azure AI Agents MVP (Orchestrator + Actions in Azure AI Foundry)

Minimal working MVP where a **Foundry Agent (orchestrator)** calls 5 lightweight HTTP **agent services** via **Actions (OpenAPI)**:

- **policy** → `policy_authorize` (checks user scopes)
- **bankingops** → `transfer_estimate`, `account_info` (stubs)
- **boleto** → `boleto_search` (returns `doc_id` for invoices/bills)
- **ragdocs** → `ragdocs_retrieve` (returns *evidence* for a given `doc_id`)
- **verifier** → `verifier_check` (validates final answer requires evidence)

**Example flow** (“Which bills are due this week?”):  
`policy.authorize → boleto.search → ragdocs.retrieve(doc_id) → verifier.check`  
Final answer includes a short list (≤5) + **Evidence** (`docId`, page, snippet).

---

## Table of Contents
- [Architecture](#architecture)
- [Repo Structure](#repo-structure)
- [Prerequisites](#prerequisites)
- [Run Locally](#run-locally)
- [Deploy to Azure Container Apps](#deploy-to-azure-container-apps)
- [Configure Actions in Azure AI Foundry](#configure-actions-in-azure-ai-foundry)
- [Test Scenarios](#test-scenarios)
- [Cost Controls](#cost-controls)
- [Troubleshooting](#troubleshooting)
- [Cleanup](#cleanup)
- [License](#license)

---

## Architecture

User → Foundry Agent (LLM Orchestrator with Actions)
├─ policy (authorization / scopes)
├─ bankingops (bank ops, stubbed)
├─ boleto (bill search → doc_id list)
├─ ragdocs (RAG evidence by doc_id)
└─ verifier (answer validation w/ evidence)
Infra: Azure Container Apps (+ ACR), optional Azure Blob Storage, optional Azure AI Search

All services expose:
- `GET /healthz` – health check
- `GET /openapi.json` – OpenAPI schema (paste into Foundry Action)

> Sample PDFs in `pdf.test/` and minimal metadata `TEST-001.json`, `TEST-002.json`.

---

## Repo Structure

app/
agents/
policy/
main.py
requirements.txt
bankingops/
main.py
requirements.txt
boleto/
main.py
requirements.txt
ragdocs/
Dockerfile
main.py
requirements.txt
verifier/
main.py
requirements.txt
common/
azure_clients.py
logging_conf.py
models.py
orchestrator/
Dockerfile
main.py
requirements.txt
infra/
bicep/
main.bicep (skeleton only)
pdf.test/
boleto1.pdf
boleto2.pdf
TEST-001.json
TEST-002.json
docker-compose.yml
requirements.txt (optional, root)


---

## Prerequisites

- Docker Desktop
- Python 3.10+ (only if you run without Docker)
- Azure CLI:
  ```bash
  az extension add -n containerapp --upgrade
  az provider register -n Microsoft.App --wait
  az provider register -n Microsoft.OperationalInsights --wait
(Optional) Azure Storage for real blob data:

STORAGE_CONN (connection string)

BOLETO_CONTAINER (e.g., boletos)

Run Locally
Option A — Docker Compose (recommended)

docker compose up --build
Health & OpenAPI (adjust ports as your compose maps):

curl http://localhost:8080/healthz          # orchestrator
curl http://localhost:8081/openapi.json      # policy
curl http://localhost:8082/openapi.json      # bankingops
curl http://localhost:8083/openapi.json      # boleto
curl http://localhost:8084/openapi.json      # ragdocs
curl http://localhost:8085/openapi.json      # verifier
Option B — Per service (without Docker)

cd app/agents/policy
pip install -r requirements.txt
uvicorn main:app --reload --port 8081
# Repeat for each folder, changing the port
Environment variables (if needed)

STORAGE_CONN="DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;"
BOLETO_CONTAINER="boletos"
LOG_LEVEL=INFO
Deploy to Azure Container Apps
Use one Resource Group and one Container Apps Environment for all services.


# Variables
RG="agents-rg"
LOC="eastus"
ENV_NAME="agents-cae"
ACR_NAME="agentsacr$RANDOM"

# Resource Group + ACA Environment + ACR
az group create -n $RG -l $LOC
az containerapp env create -g $RG -n $ENV_NAME -l $LOC
az acr create -g $RG -n $ACR_NAME --sku Basic
az acr login -n $ACR_NAME
Build & Push (example: policy)


cd app/agents/policy
docker build -t $ACR_NAME.azurecr.io/agent-policy:latest .
docker push $ACR_NAME.azurecr.io/agent-policy:latest
Create each Container App

az containerapp create -g $RG -n agent-policy \
  --environment $ENV_NAME \
  --image $ACR_NAME.azurecr.io/agent-policy:latest \
  --target-port 8080 --ingress external \
  --min-replicas 1 --max-replicas 1
Repeat for: agent-banking, agent-boleto, agent-rag, agent-verifier (and agent-orchestrator if you want to expose it).

Get FQDNs & Smoke test (PowerShell)


$RG = "agents-rg"
$apps = "agent-policy","agent-banking","agent-boleto","agent-rag","agent-verifier"

foreach ($app in $apps) {
  $fqdn = az containerapp show -g $RG -n $app --query "properties.configuration.ingress.fqdn" -o tsv
  "$app -> https://$fqdn"
  Invoke-WebRequest "https://$fqdn/healthz" -UseBasicParsing
  Invoke-WebRequest "https://$fqdn/openapi.json" -UseBasicParsing
}
Configure Actions in Azure AI Foundry
Foundry → Agents → (your Orchestrator Agent) → Actions → Add → OpenAPI
Auth method: Anonymous (for MVP). Paste each service’s /openapi.json.

Create 5 Actions:

policy

Schema: OpenAPI from https://<policy-fqdn>/openapi.json

Main op: policy_authorize

bankingops

Schema: https://<banking-fqdn>/openapi.json

boleto

Schema: https://<boleto-fqdn>/openapi.json

Main op: boleto_search

ragdocs

Schema: https://<rag-fqdn>/openapi.json

Main op: ragdocs_retrieve

Orchestrator must pass doc_id from boleto results.

verifier

Schema: https://<verifier-fqdn>/openapi.json

Main op: verifier_check

System Prompt (Orchestrator) — paste as Instructions


You are the orchestrator. Route tool calls and require evidence for any document-based claim.

Tools:
- policy.authorize: always first when reading banking/boletos.
- bankingops: estimates and account summaries.
- boleto.search: list bills by time range (default: this_week).
- ragdocs.retrieve: fetch evidence for each doc_id returned by boleto.
- verifier.check: approve final answer; if fails, revise and try again.

Answer in English with compact lists (≤5). Include an "Evidence" section with [{docId, page, snippet}] whenever documents are referenced. If data is missing, ask a clarifying question.
Test Scenarios
Bills – short list
Prompt: “Which bills are due this week?”
Expected chain: policy → boleto.search → ragdocs.retrieve(doc_id) → verifier.check
Output: short list (≤5) + Evidence (docId, page, snippet).

Cost Controls
Scale-to-zero & disable ingress (ACA)


$RG="agents-rg"
$apps="agent-policy","agent-banking","agent-boleto","agent-rag","agent-verifier"

# Allow idle to zero (keeps ingress)
foreach ($app in $apps) { az containerapp update -g $RG -n $app --min-replicas 0 --max-replicas 1 }

# Fully cut public traffic
foreach ($app in $apps) { az containerapp ingress disable -g $RG -n $app }

# Re-enable when needed
foreach ($app in $apps) { az containerapp ingress enable -g $RG -n $app --type external --target-port 8080 }
ACA storage & ACR images still incur storage cents. Delete unused images/blobs for zero.

Foundry/ML Evaluation costs: avoid running large “Safety/Evaluation” jobs; sample small subsets, use cheaper evaluators, lower token limits, and set budgets/alerts in Cost Management.

Troubleshooting
--ingress none not recognized → use az containerapp ingress disable instead.

Provider not registered → az provider register -n Microsoft.App --wait

Action save fails (400) → ensure https://<fqdn>/openapi.json is reachable and valid; keep Anonymous auth for MVP.

No replicas dropping → set min-replicas 0, then deactivate the active revision to force zero immediately:


$rev = az containerapp revision list -g $RG -n <app> --query "[?properties.active==\`true\`].name" -o tsv
foreach ($r in $rev) { az containerapp revision deactivate -g $RG -n <app> --revision $r }
Cleanup

# Nuke the whole MVP (resource group)
az group delete -n agents-rg --yes --no-wait
License
Educational MVP with stub services. Not production-ready (auth, private networking, secrets, logging, policies, etc. must be hardened).

::contentReference[oaicite:0]{index=0}