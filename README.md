# AI Agents Azure MVP (Orquestrador + Ações no Azure AI Foundry)

MVP com **orquestrador** chamando agentes via **Actions (OpenAPI)** do **Azure AI Foundry**:

- **policy** → `policy_authorize` (autoriza escopos do usuário)
- **bankingops** → `transfer_estimate`, `account_info` (stubs)
- **boleto** → `boleto_search` (retorna `doc_id`s dos boletos)
- **ragdocs** → `ragdocs_retrieve` (retorna *evidence* por `doc_id`)
- **verifier** → `verifier_check` (valida a resposta exigindo evidências)

**Fluxo sugerido (ex.: “Quais boletos vencem esta semana?”)**  
`policy.authorize → boleto.search → ragdocs.retrieve(doc_id) → verifier.check`  
Resposta final: lista (≤ 5) + **Evidências** (`docId`, página, trecho).

> Os serviços são **stubs prontos** e expõem `/healthz` e `/openapi.json`. Há PDFs de teste em `pdf.test/` e metadados `TEST-001.json`, `TEST-002.json`.

---

## Sumário

- [Arquitetura](#arquitetura)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Pré-requisitos](#pré-requisitos)
- [Rodando localmente](#rodando-localmente)
- [Deploy no Azure (Container Apps)](#deploy-no-azure-container-apps)
- [Configurar as **Actions** no Azure AI Foundry](#configurar-as-actions-no-azure-ai-foundry)
- [Cenários de teste](#cenários-de-teste)
- [Custos & Como “congelar”](#custos--como-congelar)
- [Troubleshooting rápido](#troubleshooting-rápido)
- [Limpeza](#limpeza)

---

## Arquitetura

Usuário → Orquestrador (LLM no AI Foundry, com Actions)
├─ policy (autorização/escopos)
├─ bankingops (operações bancárias fake)
├─ boleto (busca boletos → doc_id)
├─ ragdocs (evidências por doc_id)
└─ verifier (checagem de groundedness)
Infra: Azure Container Apps + (opcional) Blob Storage + (opcional) Azure AI Search

yaml
Copiar código

---

## Estrutura do repositório

app/
agents/
bankingops/
main.py
requirements.txt
boleto/
main.py
requirements.txt
policy/
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
main.bicep (esqueleto)
pdf.test/
boleto1.pdf
boleto2.pdf
TEST-001.json
TEST-002.json
docker-compose.yml
requirements.txt (raiz, opcional)

yaml
Copiar código

---

## Pré-requisitos

- Docker Desktop
- Python 3.10+ (se rodar sem Docker)
- Azure CLI:
  ```bash
  az extension add -n containerapp --upgrade
  az provider register -n Microsoft.App --wait
  az provider register -n Microsoft.OperationalInsights --wait
(Opcional) Conta de Armazenamento se quiser blobs reais:

Var STORAGE_CONN (Connection String) e BOLETO_CONTAINER (ex.: boletos)

Rodando localmente
1) Com Docker Compose (recomendado)
bash
Copiar código
docker compose up --build
# Acompanhe logs e portas mapeadas no compose
Health & OpenAPI (ajuste portas se necessário):

bash
Copiar código
curl http://localhost:8080/healthz          # orchestrator
curl http://localhost:8081/openapi.json      # policy
curl http://localhost:8082/openapi.json      # bankingops
curl http://localhost:8083/openapi.json      # boleto
curl http://localhost:8084/openapi.json      # ragdocs
curl http://localhost:8085/openapi.json      # verifier
2) Em cada serviço (sem Docker)
bash
Copiar código
cd app/agents/policy
pip install -r requirements.txt
uvicorn main:app --reload --port 8081
# Repita para cada pasta, ajustando a porta
Para usar PDFs de teste, nenhuma configuração extra é necessária; as respostas já retornam TEST-001 e TEST-002.

Deploy no Azure (Container Apps)
Sugestão: use o mesmo Resource Group e um único Environment de ACA para todos os serviços.

bash
Copiar código
# Variáveis
RG="agents-rg"
LOC="eastus"
ENV_NAME="agents-cae"
ACR_NAME="agentsacr$RANDOM"

# RG + ACA Environment + ACR
az group create -n $RG -l $LOC
az containerapp env create -g $RG -n $ENV_NAME -l $LOC
az acr create -g $RG -n $ACR_NAME --sku Basic
az acr login -n $ACR_NAME
Build & Push (exemplo: policy)
bash
Copiar código
cd app/agents/policy
docker build -t $ACR_NAME.azurecr.io/agent-policy:latest .
docker push $ACR_NAME.azurecr.io/agent-policy:latest
Criar cada Container App
bash
Copiar código
# Política (repita para os demais trocando nome/porta/imagem)
az containerapp create -g $RG -n agent-policy \
  --environment $ENV_NAME \
  --image $ACR_NAME.azurecr.io/agent-policy:latest \
  --target-port 8080 --ingress external \
  --min-replicas 1 --max-replicas 1
Repita para: agent-banking, agent-boleto, agent-rag, agent-verifier, agent-orchestrator (se desejar publicar o orquestrador como API).

Descobrir FQDNs + Smoke test (PowerShell)
ps1
Copiar código
$apps = "agent-policy","agent-banking","agent-boleto","agent-rag","agent-verifier"
$RG   = "agents-rg"

foreach ($app in $apps) {
  $fqdn = az containerapp show -g $RG -n $app --query "properties.configuration.ingress.fqdn" -o tsv
  "$app  ->  https://$fqdn"
  Invoke-WebRequest "https://$fqdn/healthz" -UseBasicParsing
  Invoke-WebRequest "https://$fqdn/openapi.json" -UseBasicParsing
}
Configurar as Actions no Azure AI Foundry
No AI Foundry → Agents → (seu agente orquestrador) → Ações → Adicionar:

Método de autenticação: Anônimo (para o MVP).
Cole o OpenAPI diretamente de https://<fqdn>/openapi.json (ou copie o JSON e cole no editor).

Crie 5 ações (um por serviço):

policy

Schema: cole o OpenAPI de agent-policy (/openapi.json)

Métodos principais: GET /healthz, POST /policy/authorize (expostos no schema como policy_authorize)

bankingops

Schema: agent-banking (/openapi.json)

boleto

Schema: agent-boleto (/openapi.json) — função boleto_search

ragdocs

Schema: agent-rag (/openapi.json) — função ragdocs_retrieve

Dica: o orquestrador deve passar doc_id recebido do boleto para o RAG.

verifier

Schema: agent-verifier (/openapi.json) — função verifier_check

Depois de adicionar as Actions, publique o agente e use o Playground para conversar.

Cenários de teste
Boletos – lista curta
Prompt: “Quais boletos vencem esta semana?”
Esperado (cadeia): policy → boleto.search → ragdocs.retrieve(doc_id) → verifier.check
Saída: lista com no máx. 5 itens + Evidências (cada uma com docId, page, snippet).

Custos & Como “congelar”
Em Azure Container Apps, você pode reduzir custo deixando minReplicas=0 (auto-scale) e até desabilitar o Ingress quando não estiver usando.

Exemplos (PowerShell):

ps1
Copiar código
$RG="agents-rg"
$apps="agent-policy","agent-banking","agent-boleto","agent-rag","agent-verifier"

# Reduz consumo (mantém Ingress habilitado)
foreach ($app in $apps) {
  az containerapp update -g $RG -n $app --min-replicas 0 --max-replicas 1
}

# Desabilitar Ingress (bloqueia tráfego público enquanto estiver parado)
foreach ($app in $apps) {
  az containerapp ingress disable -g $RG -n $app
}

# Reabilitar Ingress quando voltar a usar
foreach ($app in $apps) {
  az containerapp ingress enable -g $RG -n $app --type external --target-port 8080
}
Dica: use az containerapp replica list -g $RG -n <app> para checar se não há réplicas rodando.

Troubleshooting rápido
--ingress none não reconhecido: use az containerapp ingress disable (em vez de tentar setar none).

Microsoft.App não registrado:
az provider register -n Microsoft.App --wait

OpenAPI não carrega na Action: teste direto no FQDN https://<fqdn>/openapi.json; se OK, copie o JSON e cole manualmente.

Sem permissões na sub: garanta acesso à assinatura/RG antes de criar ACA/ACR.

Custos inesperados (ex.: Azure ML/AI Services): verifique a assinatura correta e execute:

bash
Copiar código
az resource list -o table
# Identifique serviços fora do RG do MVP (ex.: Machine Learning service)
Limpeza
bash
Copiar código
# Apagar tudo do MVP
az group delete -n agents-rg --yes --no-wait

# Se criou ACR separado:
az acr delete -n <seu-ACR> -g agents-rg
Licença & Avisos
Este projeto é um MVP educacional com serviços stub.
Não é recomendado para produção sem hardening (auth, rede privada, logs, políticas, etc.).

makefile
Copiar código
::contentReference[oaicite:0]{index=0}






Você disse:
tem que ser em ingles


O ChatGPT disse:
md
Copiar código
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

yaml
Copiar código

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

yaml
Copiar código

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
bash
Copiar código
docker compose up --build
Health & OpenAPI (adjust ports as your compose maps):

bash
Copiar código
curl http://localhost:8080/healthz          # orchestrator
curl http://localhost:8081/openapi.json      # policy
curl http://localhost:8082/openapi.json      # bankingops
curl http://localhost:8083/openapi.json      # boleto
curl http://localhost:8084/openapi.json      # ragdocs
curl http://localhost:8085/openapi.json      # verifier
Option B — Per service (without Docker)
bash
Copiar código
cd app/agents/policy
pip install -r requirements.txt
uvicorn main:app --reload --port 8081
# Repeat for each folder, changing the port
Environment variables (if needed)

env
Copiar código
STORAGE_CONN="DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;"
BOLETO_CONTAINER="boletos"
LOG_LEVEL=INFO
Deploy to Azure Container Apps
Use one Resource Group and one Container Apps Environment for all services.

bash
Copiar código
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

bash
Copiar código
cd app/agents/policy
docker build -t $ACR_NAME.azurecr.io/agent-policy:latest .
docker push $ACR_NAME.azurecr.io/agent-policy:latest
Create each Container App

bash
Copiar código
az containerapp create -g $RG -n agent-policy \
  --environment $ENV_NAME \
  --image $ACR_NAME.azurecr.io/agent-policy:latest \
  --target-port 8080 --ingress external \
  --min-replicas 1 --max-replicas 1
Repeat for: agent-banking, agent-boleto, agent-rag, agent-verifier (and agent-orchestrator if you want to expose it).

Get FQDNs & Smoke test (PowerShell)

ps1
Copiar código
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

csharp
Copiar código
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

ps1
Copiar código
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

ps1
Copiar código
$rev = az containerapp revision list -g $RG -n <app> --query "[?properties.active==\`true\`].name" -o tsv
foreach ($r in $rev) { az containerapp revision deactivate -g $RG -n <app> --revision $r }
Cleanup
bash
Copiar código
# Nuke the whole MVP (resource group)
az group delete -n agents-rg --yes --no-wait
License
Educational MVP with stub services. Not production-ready (auth, private networking, secrets, logging, policies, etc. must be hardened).

makefile
Copiar código
::contentReference[oaicite:0]{index=0}