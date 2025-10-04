from fastapi import FastAPI, HTTPException
from app.common.models import AskRequest, AskResponse, Evidence
from app.common.logging_conf import setup_logging
import httpx, os

log = setup_logging()
app = FastAPI(title="Orchestrator")

AGENT_POLICY = os.getenv("AGENT_POLICY_URL", "http://agent_policy:8080")
AGENT_BANK = os.getenv("AGENT_BANK_URL", "http://agent_bankingops:8080")
AGENT_BOLETO = os.getenv("AGENT_BOLETO_URL", "http://agent_boleto:8080")
AGENT_RAG = os.getenv("AGENT_RAG_URL", "http://agent_ragdocs:8080")
AGENT_VERIFIER = os.getenv("AGENT_VERIFIER_URL", "http://agent_verifier:8080")

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/ask", response_model=AskResponse)
async def ask(q: AskRequest):
    intent = "listar_boletos_semana" if "boleto" in q.text.lower() else "extrato"
    async with httpx.AsyncClient(timeout=30) as client:
        pr = await client.post(f"{AGENT_POLICY}/authorize", json={"user_id": q.user_id, "scope": "read:boletos"})
        if pr.status_code != 200:
            raise HTTPException(status_code=403, detail="Not authorized")
        evidences = []
        if intent == "listar_boletos_semana":
            br = await client.get(f"{AGENT_BOLETO}/search", params={"range": "this_week"})
            if br.status_code == 200:
                data = br.json()
                rr = await client.post(f"{AGENT_RAG}/retrieve", json={"query":"boletos desta semana"})
                if rr.status_code == 200:
                    for e in rr.json().get("evidence", []):
                        evidences.append(Evidence(**e))
                answer = f"Encontrei {len(data.get('items', []))} boleto(s) a vencer esta semana."
            else:
                answer = "Não consegui procurar boletos agora."
        else:
            tr = await client.get(f"{AGENT_BANK}/transactions", params={"range": "this_month"})
            count = len(tr.json().get("items", [])) if tr.status_code == 200 else 0
            answer = f"Encontrei {count} lançamentos no mês."
        vr = await client.post(f"{AGENT_VERIFIER}/check", json={"answer": answer, "evidence": [e.model_dump() for e in evidences]})
        if vr.status_code != 200:
            raise HTTPException(status_code=500, detail="Verifier failed")
        return AskResponse(answer=answer, evidence=evidences)
