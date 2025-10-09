# Azure AI Agents MVP (Orchestrator + Anonymous Actions)

A minimal **agentic** MVP where an **Azure AI Foundry Agent (orchestrator)** calls five lightweight HTTP services published on **Azure Container Apps (ACA)** via **Actions** (OpenAPI) using **Anonymous** authentication.

> This README is a single, self‑contained file you can paste into your repo. It includes:
>
> * Architecture & repo layout
> * Local run & ACA deployment
> * Cost control (freeze ACA & disable ingress)
> * **Azure AI Foundry**: full **System Prompt**, **tool wiring**, and **anonymous auth** details
> * Test scenarios and expected tool call chains

---

## Architecture

```
User → Foundry Agent (LLM Orchestrator)
          ├─ policy       → policy_authorize
          ├─ bankingops   → transfer_estimate, account_info (stubs)
          ├─ boleto       → boleto_search (returns items with doc_id)
          ├─ ragdocs      → ragdocs_retrieve (evidence by doc_id)
          └─ verifier     → verifier_check (groundedness gate)
Infra: Azure Container Apps (+ ACR). Optional: Azure Blob Storage, Azure AI Search.
All services expose: GET /healthz, GET /openapi.json
```

**Happy path** – “Which bills are due this week?”

```
policy.authorize → boleto.search(range=this_week)
  → for each item: ragdocs.retrieve(doc_id, query="…")
  → verifier.check(answer, evidence[]) → final message with ≤5 items + evidence
```

---

## Repository layout

```
app/
  agents/
    policy/
    bankingops/
    boleto/
    ragdocs/
    verifier/
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
    main.bicep (skeleton)
pdf.test/
  boleto1.pdf
  boleto2.pdf
TEST-001.json
TEST-002.json
docker-compose.yml
```

---

## Prerequisites

* **Azure CLI**

  ```powershell
  az extension add -n containerapp --upgrade
  az provider register -n Microsoft.App --wait
  ```
* **Docker** (for local & ACA builds)
* **Python 3.10+** if you want to run the services without Docker

---

## Run locally

### Option A — Individual services (dev mode)

For each folder under `app/agents/<service>`:

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1  # (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn main:app --reload --port 8080   # change port per service
```

### Option B — Docker Compose

From repo root:

```bash
docker-compose up --build
```

Each service exposes `/healthz` and `/openapi.json`.

---

## Deploy to Azure Container Apps (quick path)

> Assumes you already have an **ACR** and a **Container Apps Environment (CAE)**. If not, you can create them with Azure CLI or portal.

Build & push images (example using Docker/ACR):

```bash
# Login to ACR
az acr login -n <ACR_NAME>

# Build & push (repeat per service)
docker build -t <ACR_NAME>.azurecr.io/agent-policy:latest ./app/agents/policy
docker push <ACR_NAME>.azurecr.io/agent-policy:latest
```

Create/update Container Apps (example):

```bash
RG=<your-rg>
ENV=<your-cae-name>
IMG=<ACR_NAME>.azurecr.io/agent-policy:latest

az containerapp create \
  -g $RG -n agent-policy \
  --environment $ENV \
  --image $IMG \
  --ingress external --target-port 8080 \
  --min-replicas 1 --max-replicas 1
```

Discover FQDNs and smoke test:

```powershell
az containerapp list --query "[].{name:name,fqdn:properties.configuration.ingress.fqdn,rg:resourceGroup}" -o table
$POLICY_FQDN = az containerapp show -g <RG> -n agent-policy --query "properties.configuration.ingress.fqdn" -o tsv
Invoke-WebRequest "https://$POLICY_FQDN/healthz" -UseBasicParsing
Invoke-WebRequest "https://$POLICY_FQDN/openapi.json" -UseBasicParsing
```

Repeat for: `agent-banking`, `agent-boleto`, `agent-rag`, `agent-verifier`.

---

## Configure the Orchestrator in **Azure AI Foundry**

### 1) Create the Agent

* **Name**: Orchestrator
* **Model**: a GPT‑4 class model (e.g., `gpt-4o-mini` / `gpt-4.1-mini`) according to your availability
* **Response style**: Balanced (or Precise)

### 2) Paste the **System Prompt** (full text)

```text
You are an orchestration agent for banking operations. You have five HTTP tools:

1) policy_authorize(user_id, scope) → { ok: boolean }
   - Call this first for any action that reads or lists bills (scope: "read:boletos").

2) boleto_search(range) → { range: string, items: [{ doc_id: string }] }
   - range is natural language (e.g., "this_week", "next_week", "overdue").
   - Returns up to a few items with a unique doc_id for each bill.

3) ragdocs_retrieve(doc_id, query) → { evidence: [{ doc_id: string, page: number, snippet: string }] }
   - Given a document id from boleto_search, get a small snippet confirming due date/amount.
   - Call once per selected item; aggregate the evidence.

4) verifier_check(answer, evidence[]) → { ok: boolean }
   - Use this to validate the final answer is grounded in the retrieved evidence.

5) bankingops (transfer_estimate, account_info) → stubs for future flows.

Policy:
- Always call policy_authorize before reading boleto info.
- If authorization fails, explain the user scope required (read:boletos) and stop.
- Keep final lists ≤ 5 items.
- Always show an Evidence section with [{docId, page, snippet}] summarizing the proof.
- If ragdocs_retrieve returns empty evidence, either re-try with a clearer query or exclude that item.
- Before replying to the user, call verifier_check with the full text answer and the collected evidence.
- If verifier_check.ok == false, refine the answer or the retrieval and try again once.

Formatting:
- Use concise bullet points for lists.
- Portuguese or English according to the user’s input language.
- Do not reveal internal tool call details.
```

> Tip: keep the prompt in **Portuguese** if your users will chat in Portuguese.

### 3) Add **Actions** (Tools) — **Authentication: Anonymous**

For each service, click **Add action → OpenAPI schema** and paste the service’s `openapi.json`. Set:

* **Auth method**: **Anonymous**
* **Base URL**: the service **FQDN** (e.g., `https://agent-policy.<random>.<region>.azurecontainerapps.io`)

You should end up with **five actions** in the Agent:

* `policy`  → exposes `policy_authorize`
* `bankingops` → exposes `transfer_estimate`, `account_info`
* `boleto` → exposes `boleto_search`
* `ragdocs` → exposes `ragdocs_retrieve`
* `verifier` → exposes `verifier_check`

> In the **Foundry Actions UI**, paste the entire OpenAPI JSON content and choose **Anonymous**.

### 4) Inference settings (suggested)

* **Max output tokens**: 1024–2048
* **Temperature**: 0.2–0.5 (lower = more deterministic for tool use)
* **Top P**: default
* **Tool choice**: Auto / Let model decide

---

## Test Scenarios (Playground → Agents)

### Scenario A — Bills (short list)

**User**: *Quais boletos vencem esta semana?*

**Expected chain**: `policy_authorize → boleto_search("this_week") → ragdocs_retrieve(doc_id...) → verifier_check → final`
**Expected answer**: a list with ≤5 items and an **Evidence** section like:

```
Evidências:
- {docId: "TEST-001", página: 1, trecho: "Vencimento e valor confirmados no documento."}
- {docId: "TEST-002", página: 1, trecho: "Vencimento e valor confirmados no documento."}
```

### Scenario B — No results

**User**: *Há boletos vencendo hoje?*
If `boleto_search` returns empty, the agent replies that no bills are due today.

### Scenario C — Banking stubs

**User**: *Simule uma transferência de R$100*
The agent may call `bankingops.transfer_estimate` (stubbed) and respond accordingly.

---

## Cost Controls (ACA)

### Freeze replicas (scale to zero)

> ACA requires `max-replicas ≥ 1`. To stop runtime costs, set **min=0** so instances scale to zero when idle. Optionally disable ingress.

```powershell
$RG = "agents-rg"
$apps = "agent-policy","agent-banking","agent-boleto","agent-rag","agent-verifier"

foreach ($app in $apps) {
  az containerapp update -g $RG -n $app --min-replicas 0 --max-replicas 1
}
```

Check replicas (should empty after idling):

```powershell
foreach ($app in $apps) {
  az containerapp replica list -g $RG -n $app -o table
}
```

### Disable ingress (stop external traffic)

```powershell
foreach ($app in $apps) {
  az containerapp ingress disable -g $RG -n $app
}
```

> When you want to test again, re-enable ingress:

```powershell
az containerapp ingress enable -g $RG -n agent-policy --type external --target-port 8080
# repeat for each service as needed
```

> **Note:** If you completely shut down (min=0) **and** disable ingress, Foundry actions will fail until you re-enable ingress and ACA scales back from zero (few seconds after first hit).

---

## Azure AI Services cost note

If you used **Azure AI Foundry** evaluations or features (e.g., safety evaluations), you may see charges under **Azure Machine Learning service - Safety Evaluations Input tokens**. To reduce:

* Avoid running evaluation jobs if not needed.
* Use smaller models (e.g., `gpt-4o-mini`) during development.
* Limit token output and session length in Playground.

---

## Troubleshooting

* **Subscription not registered for Microsoft.App**

  ```bash
  az provider register -n Microsoft.App --wait
  ```
* **OpenAPI action fails**: Check that `/openapi.json` resolves publicly and that the **Base URL** in Foundry matches your ACA FQDN (https://...).
* **401/403 from services**: Actions must be **Anonymous**; ensure your service endpoints do not require auth for the MVP.
* **No evidence**: Refine the `query` sent to `ragdocs_retrieve` (e.g., "comprovar vencimento e valor do boleto").

---

## License

MIT (or your preferred license) — sample code for demonstration purposes only.
