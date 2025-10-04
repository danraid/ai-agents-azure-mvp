# Azure AI Agents MVP (Read-only)

MVP com orquestrador + agentes (policy, bankingops, boleto, ragdocs, verifier).
Stack alvo: Azure Container Apps, Blob Storage, Azure AI Search, Azure OpenAI (opcional).

Pasta `app/` contém os serviços; `infra/bicep/` é um esqueleto para IaC.

## Subir local
1. Entre em cada pasta e instale `requirements.txt`
2. Rode `uvicorn main:app --reload --port 8080` (ajuste portas por serviço)
3. Ou use `docker-compose up --build`
