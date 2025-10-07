from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Agent-RAG-Docs (stub)", version="0.2.0")

class RetrieveIn(BaseModel):
    doc_id: str
    query: str

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/retrieve")
def retrieve(body: RetrieveIn):
    # MVP: apenas ecoa o doc_id recebido e gera um trecho fictício
    return {
        "evidence": [
            {
                "doc_id": body.doc_id,
                "page": 1,
                "snippet": "Vencimento e valor confirmados no documento."
            }
        ]
    }
