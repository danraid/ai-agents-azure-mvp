## AI Agents Azure MVP (Orquestrador + Ações no Azure AI Foundry)

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